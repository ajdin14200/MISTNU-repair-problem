from pysmt.shortcuts import *
from pysmt.optimization.goal import MaximizationGoal, MinimizationGoal


def encode_min_k_budget(original_bounds, bounds):
    s = []
    #print("bounds ", bounds)
    #print(original_bounds)
    for n, lst in bounds.items():
        for i, (l, u) in enumerate(lst):
            L, U = original_bounds[n][i]
            s.append(Plus(Minus(Real(U), u), Minus(l, Real(L))))
    return Plus(s)



#This function is encode the fairness optimization function that maximizes the number of contract that are reduce by the same amount
def encode_fairness_on_contract_objective(original_bounds, bounds):
    perc_constraints = []
    # Add "Swedish" fairness constraints to the formula
    ps = []
    for name, lst in bounds.items():
        assert len(lst) == 1, "Disjunctive contingent are not supported yet"
        (L, U) = lst[0]
        p_variable = Symbol(f"{name}", REAL)
        ps.append(p_variable)
        orig_L, orig_U = original_bounds[name][0]
        perc_formula = Div(Plus(Minus(L, Real(orig_L)), Minus(Real(orig_U), U)), Real(orig_U - orig_L))
        #not_touch_formula = And(Equals(Real(orig_L), L), Equals(Real(orig_U), U))
        p_formula = Equals(p_variable, perc_formula)
        # print("p ", p_formula.serialize())
        perc_constraints.append(p_formula)
        perc_constraints.append(GE(p_variable, Real(0)))
    return And(perc_constraints), ps


#This function is encode the fairness optimization function that maximizes the number of agent that reduce their flexibility by the same amount
def encode_fairness_on_agent_objective(owners, original_bounds, bounds):
    perc_constraints = []
    # Add "Swedish" fairness constraints to the formula
    ps = []

    print(original_bounds)
    print(bounds)

    for agent_name, contracts in owners.items():

        p_variable = Symbol(f"{agent_name}", REAL)
        ps.append(p_variable)
        sum_reduction = []
        sum_flexibility = 0

        for contract in contracts:
            label = contract.atoms[0].lowerBound
            orig_L, orig_U = original_bounds[label][0]
            L,U = bounds[label][0]

            sum_reduction.append(Minus(L, Real(orig_L)))
            sum_reduction.append(Minus(Real(orig_U), U))

            sum_flexibility+= orig_U - orig_L

        perc_formula = Div(Plus(sum_reduction), Real(sum_flexibility))
        p_formula = Equals(p_variable, perc_formula)
        perc_constraints.append(p_formula)
        perc_constraints.append(GE(p_variable, Real(0)))
    return And(perc_constraints), ps


# This functin encode the k-constraint optimization function, i.e., it minimizes the number of contracts that are reduced
def encode_k_contract_objective(original_bounds, bounds):
    perc_constraints = []
    # Add "Swedish" fairness constraints to the formula
    ps = []
    for name, lst in bounds.items():
        assert len(lst) == 1, "Disjunctive contingent are not supported yet"
        (L, U) = lst[0]
        p_variable = Symbol(f"{name}", REAL)
        ps.append(p_variable)
        orig_L, orig_U = original_bounds[name][0]
        perc_formula = Plus(Minus(L, Real(orig_L)), Minus(Real(orig_U), U))
        # not_touch_formula = And(Equals(Real(orig_L), L), Equals(Real(orig_U), U))
        p_formula = Equals(p_variable, perc_formula)
        # print("p ", p_formula.serialize())
        perc_constraints.append(p_formula)
        perc_constraints.append(GE(p_variable, Real(0)))
    return And(perc_constraints), ps


def run_optimization(mistnu, formula, variables, use_optim, solver_name):
    lexicographic_optim = []

    if use_optim == "min_k_budget":
        objective = encode_min_k_budget(mistnu.B, variables)  # minimization of the reduction
        obj1 = MinimizationGoal(objective)
        lexicographic_optim.append(obj1)

    elif use_optim == "fairness_contract":  # fairness optimization

        objective = encode_min_k_budget(mistnu.B, variables)  # minimization of the reduction
        obj1 = MinimizationGoal(objective)

        p_formula, P = encode_fairness_on_contract_objective(mistnu.B, variables)
        formula = And(formula, p_formula)

        tot = []
        if len(P) > 1:
            for p1 in P:
                for p2 in P:
                    if p1 != p2:
                        tot.append(Ite(Equals(p1, p2), Real(1), Real(0)))
            obj2 = MaximizationGoal(Plus(tot))

        lexicographic_optim.append(obj1)  # First
        lexicographic_optim.append(obj2)  # Second

    elif use_optim == "k_contract":
        p_formula, P = encode_k_contract_objective(mistnu.B, variables)
        formula = And(formula, p_formula)
        tot = []
        if len(P) > 1:
            for p in P:
                tot.append(Ite(Equals(p, Real(0)), Real(1), Real(0)))
            obj1 = MaximizationGoal(Plus(tot))
        lexicographic_optim.append(obj1)

    elif use_optim == "fairness_agent":

        objective = encode_min_k_budget(mistnu.B, variables)  # minimization of the reduction
        obj1 = MinimizationGoal(objective)

        p_formula, P = encode_fairness_on_agent_objective(mistnu.owners, mistnu.B, variables)
        formula = And(formula, p_formula)

        tot = []
        if len(P) > 1:
            for p1 in P:
                for p2 in P:
                    if p1 != p2:
                        tot.append(Ite(Equals(p1, p2), Real(1), Real(0)))
            obj2 = MaximizationGoal(Plus(tot))

        lexicographic_optim.append(obj1)  # First
        lexicographic_optim.append(obj2)  # Second

    with Optimizer(name=solver_name) as opt:
        opt.add_assertion(formula)
        result = opt.lexicographic_optimize(lexicographic_optim)

        if result is None:
            raise RuntimeError("The problem is not repairable!")
        else:
            model, cost = result
            bool = False
            if model:
                bool = True

            res = {n: [(model.get_py_value(l), model.get_py_value(u)) for (l, u) in lst] for n, lst in variables.items()}

            p_res = {}
            if use_optim in ["k_contract", "fairness_contract"]:
                p_res = {n: model.get_py_value(Symbol(f"{n}", REAL)) for n in variables}

            elif use_optim == "fairness_agent":
                p_res = {n: model.get_py_value(Symbol(f"{n}", REAL)) for n in mistnu.owners.keys()}

            return bool, res, p_res, mistnu.B
