
from pysmt.shortcuts import *
from pysmt.optimization.goal import MaximizationGoal, MinimizationGoal

import sys
sys.path.insert(0, '..')
from structures import *

sys.path.append('checking_algorithm')
from wc_checking_algorithm import *




# We transform each cSTNU (one per agent) to an STNU by replacing each label on edges by the actual duration of the contract
def cSTNU_to_STNU(network, B, map_contracts):


    constraints = set()
    for constraint in network.constraints:
        if constraint.contract:

            source = constraint.atoms[0].source
            dest = constraint.atoms[0].dest
            l = B[constraint.atoms[0].lowerBound][0][0]
            u =  B[constraint.atoms[0].upperBound][0][1]
            map_contracts[source.name+"_"+dest.name] = constraint.atoms[0].lowerBound
            at = AtomicConstraint(source,dest,l,u)
            atoms = set()
            atoms.add(at)
            new_constraint = Constraint(atoms, True, constraint.contract, constraint.fixBinary())
            constraints.add(new_constraint)

        else:
            constraints.add(constraint)

    new_network = Network()
    new_network.timePoints = network.timePoints
    new_network.constraints = constraints
    new_network.vz = network.vz

    return new_network

# This function check the Weak Controllability (WC) of each network (STNU)
# It is based on the latest most efficient algorithm for checking WC from Ajdin Sumic and Thierry Vidal 2024
# This new WC checking algorithm returns for an STNU its negative cycle if not weakly controllable
# Please note that each cycle is compose of a min and a max path where the min representive the positive path in the negative cycle from v_i to v_j
# while the max path the negative path in the negative cycle from v_j to v_i. This is due to the way the search is done in the WC-Checking algorithm
def compute_controllability(mistnu):
    agent_cycles = {}
    map_contracts = {}
    for i in range (len(mistnu.networks)):
        network = cSTNU_to_STNU(mistnu.networks[i], mistnu.B, map_contracts)
        cycles = check_weak(network)
        agent_cycles[mistnu.agents[i].name] = cycles
    return agent_cycles, map_contracts

# encode the contract (process) in the min path of the negative cycle
def compute_min_path_formula(path, map_contracts,contracts_variables, variables, cycle_variables):
    sum = []
    for contingent in path[1]:
        if contingent.contract:
            source = contingent.atoms[0].source.name
            dest = contingent.atoms[0].dest.name
            l = contingent.atoms[0].lowerBound
            u = contingent.atoms[0].upperBound

            if l<0: # if inverse contingent then l and u are inversed
                contract_variable = contracts_variables[map_contracts[dest+"_"+source]][0]
                sum.append(Minus(Real(u*-1), contract_variable[0]))
                variables.add(contract_variable[0])
                cycle_variables.add(contract_variable[0])

            else:
                contract_variable = contracts_variables[map_contracts[source+"_"+dest]][0]
                sum.append(Minus(Real(u),contract_variable[1]))
                variables.add(contract_variable[1])
                cycle_variables.add(contract_variable[1])
    return sum

# encode the contract (process) in the max path of the negative cycle
def compute_max_path_formula(path, map_contracts,contracts_variables, variables, cycle_variables):
    sum = []
    for contingent in path[1]:
        if contingent.contract:
            source = contingent.atoms[0].source.name
            dest = contingent.atoms[0].dest.name
            l = contingent.atoms[0].lowerBound
            u = contingent.atoms[0].upperBound


            if l < 0:  # if inverse contingent then l and u are inversed
                contract_variable = contracts_variables[map_contracts[dest+"_"+source]][0]
                sum.append(Minus(Real(l*-1), contract_variable[1]))
                variables.add(contract_variable[1])
                cycle_variables.add(contract_variable[1])


            else:
                contract_variable = contracts_variables[map_contracts[source+"_"+dest]][0]
                sum.append(Minus(contract_variable[0], Real(l)))
                variables.add(contract_variable[0])
                cycle_variables.add(contract_variable[0])

    return sum
# This function return the encoding of a negative cycle by merging the encoding from the min and max path
def compute_cycle_formula(cycle, map_contracts,contracts_variables, variables):
    min_p = cycle[0]
    max_p = cycle[1]

    flexibility = min_p[0] - max_p[0]

    # min_path
    cycle_variables = set()
    min_formula = compute_min_path_formula(min_p, map_contracts,contracts_variables, variables, cycle_variables)
    max_formula = compute_max_path_formula(max_p, map_contracts,contracts_variables, variables, cycle_variables)
    sum_cycle = min_formula + max_formula
    cycle_formula = GE(Plus(sum_cycle), Real(flexibility))
    return And(cycle_formula)

# This function encode all the negative cycle of one agent, i.e., to the network (cSTNU) of the agent
def compute_agent_formula(cycles, map_contracts,contracts_variables, variables):
    # here we need to identify the constraint that are alone to prune the domain
    agent_formula = []
    for cycle in cycles:
        cycle_formula = compute_cycle_formula(cycle, map_contracts,contracts_variables, variables)
        agent_formula.append(cycle_formula)
    return And(agent_formula)


    return formula  # I return the formula itself


# This function encodes all the negative cycles (from all agents)
def get_agents_formulas(agent_cycles, map_contracts,contracts_variables):

    formula = []
    variables = set()
    for agent_name, cycles in agent_cycles.items():
        agent_formula = compute_agent_formula(cycles, map_contracts,contracts_variables, variables)
        formula.append(agent_formula)
    return And(formula), variables

# This function creates the variables of the bounds of the contracts
def create_contracts_variables(B):
    contract_variables= {}

    for label, bounds in B.items():
        contract_variables[label] = []
        for i, (L, U) in enumerate(bounds):
            LB = Symbol("LB_" + label + "_" + str(i), REAL)
            UB = Symbol("UB_" + label + "_" + str(i), REAL)
            contract_variables[label].append([LB, UB])
    return contract_variables

# This function is the encoding of the variables of the bounds of the contracts
def get_variables_formula(B, variables, contract_variables):

    variables_formula = []
    for label, bounds in B.items():

        for i, (L, U) in enumerate(bounds):
            LB = contract_variables[label][i][0]
            UB = contract_variables[label][i][1]
            bounds_formula = []

            if LB in variables and UB in variables:
                bounds_formula.append(GE(LB,Real(L)))
                bounds_formula.append(GE(UB,LB))
                bounds_formula.append(GE(Real(U),UB))

            else:

                if LB in variables:
                    bounds_formula.append(GE(LB, Real(L)))
                    bounds_formula.append(GE(Real(U), LB))
                    bounds_formula.append(Equals(UB, Real(U)))

                else:
                    bounds_formula.append(GE(UB, Real(L)))
                    bounds_formula.append(GE(Real(U), UB))
                    bounds_formula.append(Equals(LB,Real(L)))

            variables_formula.append(And(bounds_formula))
    return And(variables_formula)

# This function is the optimization function that minimizes the reduction of the bounds of the contracts
def primary_objective(original_bounds, bounds):
    s = []

    for n, lst in bounds.items():
        for i, (l, u) in enumerate(lst):  # We assume a list of bounds for future research that will adapt the case of DTNU
            L, U = original_bounds[n][i]
            s.append(Plus(Minus(Real(U), u), Minus(l, Real(L))))
    return Plus(s)



# This function is the optimization function that maximizes the number of contracts that are reduce by the same amount
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
        #print("original bounds ",orig_L, orig_U)
        #print("new bounds ",L, U)
        perc_formula = Div(Plus(Minus(L, Real(orig_L)), Minus(Real(orig_U), U)), Real(orig_U - orig_L))
        #not_touch_formula = And(Equals(Real(orig_L), L), Equals(Real(orig_U), U))
        p_formula = Equals(p_variable, perc_formula)
        #print("p ", p_formula.serialize())
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




# This function is the centralized algorithm that repairs all the negative cycles using z3 as a solver

def repair_cycle(mistnu, agent_cycles, map_contracts , SMT_solver, use_optim):

    contract_variables = create_contracts_variables(mistnu.B) # I create a variable for each bound of each contract
    all_cycles_formula, variables = get_agents_formulas(agent_cycles, map_contracts, contract_variables) # I encode all the inconsistent cycle
    variables_formula = get_variables_formula(mistnu.B, variables, contract_variables) # I encode the variables
    #print(variables_formula)

    formula = And(all_cycles_formula, variables_formula)

    lexicographic_optim = []

    if use_optim == "min_k_budget":
        objective = primary_objective(mistnu.B, contract_variables)  # minimization of the reduction
        obj1 = MinimizationGoal(objective)
        lexicographic_optim.append(obj1)

    elif use_optim == "fairness":  # fairness optimization

        objective = primary_objective(mistnu.B, contract_variables)  # minimization of the reduction
        obj1 = MinimizationGoal(objective)

        p_formula, P = encode_fairness_on_contract_objective(mistnu.B, contract_variables)
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
        p_formula, P = encode_k_contract_objective(mistnu.B, contract_variables)
        formula = And(formula, p_formula)
        tot = []
        if len(P) > 1:
            for p in P:
                tot.append(Ite(Equals(p, Real(0)), Real(1), Real(0)))
            obj1 = MaximizationGoal(Plus(tot))
        lexicographic_optim.append(obj1)

    elif use_optim == "fairness_agent":

        objective = primary_objective(mistnu.B, contract_variables)  # minimization of the reduction
        obj1 = MinimizationGoal(objective)

        p_formula, P = encode_fairness_on_agent_objective(mistnu.owners, mistnu.B, contract_variables)
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




    #print(formula.serialize())

    with Optimizer(name=SMT_solver) as opt:
        opt.add_assertion(formula)
        result = opt.lexicographic_optimize(lexicographic_optim)

        if result is None:
            raise RuntimeError("The problem is not repairable!")
            return False, None, None, None # used for testing all benchmark

        else:
            model, cost = result
            res = {n: [(model.get_py_value(l), model.get_py_value(u)) for (l, u) in lst] for n, lst in contract_variables.items()}

            p_res = {}
            if use_optim in ["k_contract", "fairness"]:
                p_res = {n: model.get_py_value(Symbol(f"{n}", REAL)) for n in contract_variables}

            elif use_optim == "fairness_agent":
                p_res = {n: model.get_py_value(Symbol(f"{n}", REAL)) for n in mistnu.owners.keys()}

            return True, res, p_res, mistnu.B












