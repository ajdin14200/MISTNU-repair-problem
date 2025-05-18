# This file show the linear Strong repair encoding for MISTNU
# This could have been done by adding few lines in the SMT version
# For clarity, we create a new file even if it amounts to duplicate some code.

from src.optimization_functions import *
from src.centralized_algorithm.main_smt import  *





def encoding_requirements(network, controllables, chain_formulas_map, controllability, bounds):

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


            formula.append(GE(Minus(vd, vs), l))
            formula.append(LE(Minus(vd, vs), u))
    return And(formula)

def encode_network(network, bounds, controllability):

    controllables, contingent_durations = get_timepoints_variables(network)
    parents_map = get_variables_parent(network) # get parent for chain of contingents
    chain_formulas_map = get_chain_formulas(parents_map, controllables, contingent_durations)  # encode chains of contracts:  Z -u-> C -v-> D, we have D = Z + u + v

    #print("controllables ", controllables)
    #print("contingent durations ", contingent_durations)
    #print("parent map ", parents_map)
    #print("chain formulas ",chain_formulas_map)
    #print("contingent duration bounds ",contingent_duration_bounds)
    #print("bounds ", bounds)

    formula = encoding_requirements(network, controllables, chain_formulas_map, controllability, bounds)

    return And(formula)



def repair_linear(mistnu, solver_name, use_optim):
    contract_formula, bounds = encode_process(mistnu.B)
    # print(contract_formula, bounds)

    problems_formula = []
    for agent, network in zip(mistnu.agents, mistnu.networks):
        formula = encode_network(network, bounds)
        problems_formula.append(formula)

    formula = And(problems_formula + [contract_formula])
    return run_optimization(mistnu, formula, bounds, use_optim, solver_name)
