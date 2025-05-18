
from pysmt.shortcuts import *
from pysmt.optimization.goal import MaximizationGoal, MinimizationGoal

import sys
sys.path.insert(0, '..')
from structures import *

sys.path.append('checking_algorithm')
from wc_checking_algorithm import *
from src.optimization_functions import *





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


# This function is the centralized algorithm that repairs all the negative cycles using z3 as a solver

def repair_cycle(mistnu, agent_cycles, map_contracts , solver_name, use_optim):

    contract_variables = create_contracts_variables(mistnu.B) # I create a variable for each bound of each contract
    all_cycles_formula, variables = get_agents_formulas(agent_cycles, map_contracts, contract_variables) # I encode all the inconsistent cycle
    variables_formula = get_variables_formula(mistnu.B, variables, contract_variables) # I encode the variables
    #print(variables_formula)

    formula = And(all_cycles_formula, variables_formula)

    return run_optimization(mistnu,formula, contract_variables, use_optim, solver_name)











