import copy
import itertools

from pysmt.shortcuts import *
from pysmt.typing import *
from pysmt.optimization.goal import MaximizationGoal, MinimizationGoal


from src.structures import *


def encode_process(B):
    bounds = {}
    formula = []
    for label, (lst) in B.items():
        bounds[label] = []
        for i, (l, u) in enumerate(lst):
            LB = Symbol("LB_" + label + "_" + str(i), REAL)
            UB = Symbol("UB_" + label + "_" + str(i), REAL)
            bounds[label].append([LB, UB])
            formula.append(GE(LB, Real(l)))
            formula.append(GE(UB, LB))
            formula.append(LE(UB, Real(u)))
    return And(formula), bounds


def owned_contract_as_contingent(network):
    constraints = set()
    timePoints = copy.deepcopy(network.timePoints)

    for constraint in network.constraints:
        if constraint.contract == True and constraint.contingent == False:

            source = constraint.atoms[0].source
            dest = constraint.atoms[0].dest
            l = constraint.atoms[0].lowerBound
            u = constraint.atoms[0].upperBound

            new_dest = TimePoint(dest.name, False)
            timePoints[dest.name] = new_dest
            #print("test ", dest.name, new_dest.controllable)


            at = AtomicConstraint(source, new_dest, l, u)
            atoms = set()
            atoms.add(at)

            new_constraint = Constraint(atoms, True, constraint.contract, constraint.fixBinary())
            constraints.add(new_constraint)


            #print(l)

        else:
            constraints.add(constraint)

    new_network = Network()
    new_network.timePoints = timePoints
    new_network.constraints = constraints
    new_network.vz = network.vz


    return new_network


def get_timepoints_variables(network):

    controllables = {}  # map timepoint's name to variable
    contingent_durations = {} # map contingent duration to variable

    for name,tp in network.timePoints.items():
        variable = Symbol(name, REAL)

        if tp.controllable:
            controllables[name] = variable
        else:
            contingent_durations[name] = variable
    return controllables, contingent_durations


def get_variables_parent(network):

    parents_map = {}
    for constraint in network.constraints:

        if constraint.contingent:
            source = constraint.atoms[0].source.name
            dest = constraint.atoms[0].dest.name
            parents_map[dest] = source


    return parents_map


def get_chain_formulas(parents_map, controllables, contingent_durations):
    chain_formulas_map = {}

    for tp, father in parents_map.items():
        z = father
        chain = [contingent_durations[tp]]
        while z not in controllables:
            chain.append(contingent_durations[z])
            z = parents_map[z]
        chain.append(controllables[z])
        chain_formulas_map[tp] = Plus(chain)

    return chain_formulas_map

# The code can be optimize by getting all information in one loop only on constraints, but for clarity we devide each important step even do it means looping multiple time on the network's constraints.
def get_variables_bounds(network, bounds):
    contingent_duration_bounds= {}
    for constraint in network.constraints:

        if constraint.contingent:
            l = constraint.atoms[0].lowerBound
            u = constraint.atoms[0].upperBound
            ctg_tp = constraint.atoms[0].dest.name

            if constraint.contract:
                (LB, UB) = bounds[l][0]
                contingent_duration_bounds[ctg_tp]= [LB, UB]
            else:
                contingent_duration_bounds[ctg_tp]= [l, u]
    return contingent_duration_bounds


def encoding_requirements(network, controllables, chain_formulas_map):

    formula = []
    for constraint in network.constraints:

        if constraint.contingent == False:

            source = network.timePoints[constraint.atoms[0].source.name]
            dest = network.timePoints[constraint.atoms[0].dest.name]
            l = constraint.atoms[0].lowerBound
            u = constraint.atoms[0].upperBound

            #print(source.name, source.controllable)
            #print(dest.name, source.controllable)
            #print(l)
            #print(u)

            vs = None
            vd = None

            # Here we test the controllability of each timepoints.
            # Note that we didn't update all the constraint in the owned_contract_as_contingent() function as we can bypass this using the set of timepoints
            if source.controllable and dest.controllable:

                vs = controllables[source.name]
                vd = controllables[dest.name]

            elif source.controllable and dest.controllable == False:
                vs = controllables[source.name]
                vd = chain_formulas_map[dest.name]

            elif source.controllable == False and dest.controllable:
                vs = chain_formulas_map[source.name]
                vd = controllables[dest.name]

            else:
                vs = chain_formulas_map[source.name]
                vd = chain_formulas_map[dest.name]

            formula.append(GE(Minus(vd, vs), Real(l)))
            formula.append(LE(Minus(vd, vs), Real(u)))
    return And(formula)

def my_product(bounds):
    for t in itertools.product(*[v for v in bounds.values()]):
        yield dict(zip((Symbol(f"{x}",REAL) for x in bounds.keys()), t))

def encode_network(network, bounds):

    controllables, contingent_durations = get_timepoints_variables(network)
    parents_map = get_variables_parent(network) # get parent for chain of contingents
    chain_formulas_map = get_chain_formulas(parents_map, controllables, contingent_durations)  # encode chains of contracts:  Z -u-> C -v-> D, we have D = Z + u + v
    contingent_duration_bounds = get_variables_bounds(network, bounds) # for each contingent variable associate LB/UB variable if contract, else real bounds' value

    #print("controllables ", controllables)
    #print("contingent durations ", contingent_durations)
    #print("parent map ", parents_map)
    #print("chain formulas ",chain_formulas_map)
    #print("contingent duration bounds ",contingent_duration_bounds)

    formula = encoding_requirements(network, controllables, chain_formulas_map)
    #print("formula ", formula)
    projections_formula= []
    for m in my_product(contingent_duration_bounds):

        tmp_controllables = [FreshSymbol(REAL) for _ in controllables.values()]
        m.update(zip(controllables.values(), tmp_controllables))
        projections_formula.append(formula.substitute(m))

    #print("formula ",projections_formula)
    return And(projections_formula)


def primary_objective(original_bounds, bounds):
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


def onbounds(mistnu, solver_name, use_optim):
    contract_formula, bounds = encode_process(mistnu.B)
    #print(contract_formula, bounds)

    problems_formula = []
    for agent, network in zip(mistnu.agents, mistnu.networks):
        new_network = owned_contract_as_contingent(network)  # I transform all contract as contingent for checking WC
        formula= encode_network(new_network, bounds)
        problems_formula.append(formula)

    formula = And(problems_formula + [contract_formula])

    lexicographic_optim = []

    if use_optim == "min_k_budget":
        objective = primary_objective(mistnu.B, bounds) # minimization of the reduction
        obj1 = MinimizationGoal(objective)
        lexicographic_optim.append(obj1)

    elif use_optim == "fairness_contract": #fairness optimization

        objective = primary_objective(mistnu.B, bounds)  # minimization of the reduction
        obj1 = MinimizationGoal(objective)

        p_formula, P = encode_fairness_on_contract_objective(mistnu.B, bounds)
        formula = And(formula, p_formula)

        tot = []
        if len(P) > 1:
            for p1 in P:
                for p2 in P:
                    if p1 != p2:
                        tot.append(Ite(Equals(p1, p2), Real(1), Real(0)))
            obj2 = MaximizationGoal(Plus(tot))

        lexicographic_optim.append(obj1) # First
        lexicographic_optim.append(obj2) # Second

    elif use_optim == "k_contract":
        p_formula, P = encode_k_contract_objective(mistnu.B, bounds)
        formula = And(formula, p_formula)
        tot = []
        if len(P) > 1:
            for p in P:
                tot.append(Ite(Equals(p, Real(0)), Real(1), Real(0)))
            obj1 = MaximizationGoal(Plus(tot))
        lexicographic_optim.append(obj1)

    elif use_optim == "fairness_agent":

        objective = primary_objective(mistnu.B, bounds)  # minimization of the reduction
        obj1 = MinimizationGoal(objective)

        p_formula, P = encode_fairness_on_agent_objective(mistnu.owners, mistnu.B, bounds)
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

            res = {n: [(model.get_py_value(l), model.get_py_value(u)) for (l, u) in lst] for n, lst in bounds.items()}

            p_res = {}
            if use_optim in ["k_contract", "fairness_contract"]:
                p_res = {n: model.get_py_value(Symbol(f"{n}", REAL)) for n in bounds}

            elif use_optim == "fairness_agent":
                p_res = {n: model.get_py_value(Symbol(f"{n}", REAL)) for n in mistnu.owners.keys()}

            return bool,res, p_res, mistnu.B
