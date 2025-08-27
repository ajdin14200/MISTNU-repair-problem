import sys
sys.path.insert(0, '../')
from structures import *

sys.path.append('checking_algorithm')
from checking_algorithm.wc_checking_algorithm import *







import time

from structures import *
from pysmt.shortcuts import *
from pysmt.optimization.goal import MaximizationGoal




def create_contracts_variables(B, owners):
    contract_variables = {}
    agent_variables= {}
    variables_bounds = {}
    for agent, contracts in owners.items():
        agent_variables[agent] =set()

    for label, bounds in B.items():
        label_variable = Symbol(label, INT)
        contract_variables[label] = label_variable
        variables_bounds[label_variable] =[bounds[0][0], bounds[0][1]]

        for agent, contracts in owners.items():
            for contract in contracts:
                if contract.atoms[0].lowerBound == label:
                    agent_variables[agent].add(label_variable)

    return contract_variables, agent_variables, variables_bounds

def share_cycle(agent_cycles, map_contracts, readers, map_contract_owner):

    new_agent_cycles = {}
    list_invovled_contract = []
    for agent in agent_cycles.keys():
        new_agent_cycles[agent] = []

    for agent, cycles in agent_cycles.items():
        new_cycles = new_agent_cycles[agent]
        for cycle in cycles:
            agents = []
            for contingent in cycle[0][1] + cycle[1][1]:
                if contingent.contract:
                    source = contingent.atoms[0].source.name
                    dest = contingent.atoms[0].dest.name
                    l = contingent.atoms[0].lowerBound

                    contract_label = map_contracts[dest+"_"+source] if l<0 else map_contracts[source+"_"+dest]
                    if contract_label not in list_invovled_contract:
                        list_invovled_contract.append(contract_label)

                    if agent in readers[contract_label]: #agent is a reader
                        owner = map_contract_owner[contract_label]
                        if owner not in agents:
                            new_agent_cycles[owner].append(cycle)
                            agents.append(owner)


                    if map_contract_owner[contract_label] == agent and agent not in agents:
                        new_cycles.append(cycle)
                        agents.append(agent)

    return new_agent_cycles, list_invovled_contract





def create_map_contracts_owners(owners):
    map_contract_owner = {}
    for agent, contracts in owners.items():
        for contract in contracts:
            map_contract_owner[contract.atoms[0].lowerBound] = agent
    return  map_contract_owner

def sort_cycles(agent_cycles):  # this function separe for each agent the cycle only he can repair and those he need to negotiate
    agent_shared_cycles = {}
    single_agent_cycles = {}
    for agent, cycles in agent_cycles.items():
        shared = []
        single = []
        for cycle in cycles:
            if len(cycle[0][1]+cycle[1][1]) > 1:
                shared.append(cycle)
            else:
                single.append(cycle)

        agent_shared_cycles[agent] = shared
        single_agent_cycles[agent] = single
    return agent_shared_cycles, single_agent_cycles

def set_variables_bounds(single_agent_cycles, B, map_contract, contracts_variables, variable_bounds):

    variable_to_change = {}
    for agent, cycles in single_agent_cycles.items():
        for cycle in cycles:
            to_recover = cycle[0][0] - cycle[1][0]
            if len(cycle[0][1])>0: #min path
                contract = cycle[0][1][0]
                source = contract.atoms[0].source.name
                dest = contract.atoms[0].dest.name
                l = contract.atoms[0].lowerBound
                u = contract.atoms[0].upperBound
                label = ""
                if l < 0:  # if inverse contingent then l and u are inversed
                    label = map_contract[dest + "_" + source]
                    contract_variable = contracts_variables[label]
                    if contract_variable not in variable_to_change:
                        variable_to_change[contract_variable] = [to_recover, 0]
                    else:
                        if to_recover > variable_to_change[contract_variable][0]:
                            variable_to_change[contract_variable] = [to_recover, variable_to_change[contract_variable][1]]




                else:
                    label = map_contract[source + "_" + dest]
                    contract_variable = contracts_variables[label]

                    if contract_variable not in variable_to_change:
                        variable_to_change[contract_variable] = [0, to_recover]
                    else:
                        if to_recover > variable_to_change[contract_variable][1]:
                            variable_to_change[contract_variable] = [variable_to_change[contract_variable][0], to_recover]


            else: #max path

                contract = cycle[1][1][0]
                source = contract.atoms[0].source.name
                dest = contract.atoms[0].dest.name
                l = contract.atoms[0].lowerBound
                u = contract.atoms[0].upperBound
                label = ""
                if l < 0:  # if inverse contingent then l and u are inversed
                    label = map_contract[dest + "_" + source]
                    contract_variable = contracts_variables[label]
                    if contract_variable not in variable_to_change:
                        variable_to_change[contract_variable] = [0, to_recover]
                    else:
                        if to_recover > variable_to_change[contract_variable][1]:
                            variable_to_change[contract_variable] = [variable_to_change[contract_variable][0],to_recover]


                else:
                    label = map_contract[source + "_" + dest]
                    contract_variable = contracts_variables[label]
                    if contract_variable not in variable_to_change:
                        variable_to_change[contract_variable] = [to_recover, 0]
                    else:
                        if to_recover > variable_to_change[contract_variable][0]:
                            variable_to_change[contract_variable] = [to_recover, variable_to_change[contract_variable][1]]


    for variable, (recover_l, recover_u) in variable_to_change.items():
        l = variable_bounds[variable][0]
        u = variable_bounds[variable][1]
        variable_bounds[variable] = [l+recover_l, u - recover_u]

def check_variable_bounds(variables_bounds, contract_variable):

    for label, variable in contract_variable.items():
        if variables_bounds[variable][0] > variables_bounds[variable][1]:
            return False
    return True

def compute_agent_ranking(map_formula, map_contracts, contracts_variables): # the more cycle a variables is included in the strictier it is

    variables_ranking = {}

    for agent, cycles in map_formula.items():

        for cycle in cycles:

            for contract in cycle[0][1] + cycle[1][1]:
                source = contract.atoms[0].source.name
                dest = contract.atoms[0].dest.name
                l = contract.atoms[0].lowerBound
                label = map_contracts[dest + "_" + source] if l < 0 else map_contracts[source + "_" + dest]
                contract_variable = contracts_variables[label]
                if contract_variable in variables_ranking:
                    variables_ranking[contract_variable] +=1
                else:
                    variables_ranking[contract_variable] = 1

    # here I create the list of ranking among the variables
    rank = []
    for i in range(len(variables_ranking)):
        keys = list(variables_ranking.keys())
        values = list(variables_ranking.values())
        min_value = min(values)
        index_value = values.index(min_value)
        variable = keys[index_value]
        rank.append(variable)
        del variables_ranking[variable]


    return rank



def run(mistnu, agent_cycles, map_contracts):

    #print("test: readers", mas.readers)
    #print("test: owners", mas.owners)
    map_contract_owner = create_map_contracts_owners(mistnu.owners)
    #print("map contract owner ", map_contract_owner)


    contracts_variables, agent_variables, variables_bounds  = create_contracts_variables(mistnu.B, mistnu.owners)
    #print("contract variable ",contracts_variables)
    #print("agent variable ",agent_variables)
    #print("variable bounds ",variables_bounds)
    #print("map contracts ", map_contracts)
    #print("size agent_cycles ", len(agent_cycles))
    #print("agent_cycles ", agent_cycles)
    agent_cycles, list_involved_contract = share_cycle(agent_cycles, map_contracts, mistnu.readers, map_contract_owner)
    #print("list involved_contract ", list_involved_contract)



    agent_shared_cycles, single_agent_cycles = sort_cycles(agent_cycles)
    #print("variable bounds ",variables_bounds)
    set_variables_bounds(single_agent_cycles, mistnu.B, map_contracts, contracts_variables, variables_bounds)
    #print("variable bounds after solving local constraint ",variables_bounds)

    #print(agent_shared_cycles)
    rank = compute_agent_ranking(agent_cycles, map_contracts, contracts_variables)
    #rank.reverse()   Here if you want to reverse the order of agents
    #print("rank ", rank)
    #print("***********************************************")

    assignement = run_synchronous_backtracking(variables_bounds, agent_cycles, map_contracts, contracts_variables, rank, map_contract_owner)
    print("No solution exist !!!!") if len(assignement) == 0 else print("A solution exist ! The solution is : ", assignement)
    return False if len(assignement) == 0 else True






def compute_min_path_formula(contracts, map_contracts,contracts_variables):
    sum = []
    for contingent in contracts:
        if contingent.contract:
            source = contingent.atoms[0].source.name
            dest = contingent.atoms[0].dest.name
            l = contingent.atoms[0].lowerBound
            u = contingent.atoms[0].upperBound

            if l<0: # if inverse contingent then l and u are inversed
                contract_variable = contracts_variables[map_contracts[dest+"_"+source]]
                sum.append(Minus(contract_variable, Int(u*-1)))


            else:
                contract_variable = contracts_variables[map_contracts[source+"_"+dest]]
                sum.append(Minus(Int(u),contract_variable))

    return sum


def compute_max_path_formula(contracts, map_contracts,contracts_variables):
    sum = []
    for contingent in contracts:
        if contingent.contract:
            source = contingent.atoms[0].source.name
            dest = contingent.atoms[0].dest.name
            l = contingent.atoms[0].lowerBound
            u = contingent.atoms[0].upperBound


            if l < 0:  # if inverse contingent then l and u are inversed
                contract_variable = contracts_variables[map_contracts[dest+"_"+source]]
                sum.append(Minus(Int(l*-1), contract_variable))



            else:
                contract_variable = contracts_variables[map_contracts[source+"_"+dest]]
                sum.append(Minus(contract_variable, Int(l)))


    return sum

def compute_cycle_formula(cycle, map_contracts,contracts_variables):
    min_p = cycle[0]
    max_p = cycle[1]

    flexibility = min_p[0] - max_p[0]

    # min_path
    min_formula = compute_min_path_formula(min_p[1], map_contracts,contracts_variables)
    max_formula = compute_max_path_formula(max_p[1], map_contracts,contracts_variables)
    sum_cycle = min_formula + max_formula
    return Plus(sum_cycle), flexibility


def compute_agent_formula(cycles, map_contracts,contracts_variables):
    # here we need to identify the constraint that are alone to prune the domain
    formula = []
    for cycle in cycles:
        cycle_formula, flexibility = compute_cycle_formula(cycle, map_contracts,contracts_variables)
        formula.append([cycle_formula, flexibility])


    return formula  # I return the formula itself





def get_variables_formula(current_variable, assignment, variables_bounds):

    variables_formula = []

    for variable, value in assignment.items():
        variables_formula.append(Equals(variable, Int(assignment[variable])))

    real_l = variables_bounds[current_variable][0]
    real_u = variables_bounds[current_variable][1]

    variables_formula.append(GE(current_variable, Int(real_l)))
    variables_formula.append(GE(Int(real_u), current_variable))



    return variables_formula





def local_assignement(formula_to_satisfy, formula_to_forget,  variables_bounds, current_variable, assignement, restrictions):
    sum_formula_to_satisfy = []
    sum_formula_to_forget = [Int(0)]
    cycle_equation_flexibility = [Int(0)]
    variables_formula = get_variables_formula(current_variable, assignement,  variables_bounds)
    #print("variables_formula ",variables_formula)

    for (sum_cycle, flexibility) in formula_to_satisfy:
        #print(sum_cycle)
        sum_formula_to_satisfy.append(GE(sum_cycle, Int(flexibility)))

    for (sum_cycle, flexibility) in formula_to_forget:
        #print("sum cycle", sum_cycle)
        sum_formula_to_forget.append(Ite(GE(sum_cycle, Int(flexibility)), Int(1), Int(0)))
        cycle_equation_flexibility.append(Ite(LT(sum_cycle, Int(flexibility)), sum_cycle, Int(0)))
    #print(cycle_equation_iter)

    #print("to satisfy ",sum_formula_to_satisfy)
    #print(sum_formula_to_forget)
    #print(cycle_equation_flexibility)
    #print(" sum formula ", sum_formula)
    obj1 = MaximizationGoal(Plus(sum_formula_to_forget))
    obj2 = MaximizationGoal(Plus(cycle_equation_flexibility))
    #print("obj1 ",obj1)
    #print("obj2 ",obj2)
    #print("restriction: ", restrictions)
    with Optimizer("z3") as opt:
        if len(restrictions) == 0:
            opt.add_assertion(And(sum_formula_to_satisfy + variables_formula))
        else:
            opt.add_assertion(And(sum_formula_to_satisfy + variables_formula + restrictions))
        model = opt.lexicographic_optimize([obj1, obj2])
    #print("model: ", model)
    #print("value ",int(model[0].get_py_value(current_variable)))

    if model == None :
        return None

    else:
        return int(model[0].get_py_value(current_variable))

#solution to keep: We are trying to find a fixed duration of some contracts such that all networks are controllable, i.e., can the agent agree on a duration of some contract to recover controllability
# First need to create clusters of agent to independently solves the problems
# Second find the right ranking among the agent of the cluster
# To do, how to do the backtracking correctly, one it's done the rest is easy
# To do the backtracking you find the equation that is not satisfy and you select the agent in order of the ranking and if the variable of the agent is not reduce to the maximum then you add another constraint
# future work could try to find the smallest reduction required to recover controllability to all agent and if possible to make it fair among the agent, i.e., reduce the same amount the contract among agent


def check_conflict(variable,assignment, agent_formula):
        sum_formula = []
        agent_cycles = agent_formula[0]
        agent_variables = agent_formula[1]
        for (sum_cycle, flexibility, cycle_variables) in agent_cycles:
            if variable in cycle_variables:

                sum_formula.append(GE(sum_cycle, Int(flexibility)))

        variables_formula=[]
        for variable in agent_variables:
            variables_formula.append(Equals(variable, Int(assignment[variable])))

        model = get_model(And(sum_formula + variables_formula))
        #print(model)

        return  False if model else True # if a model exist then no conflit and return false, else there is a conflict, i.e., one cycle is not repaired and return True



def get_required_cycles(assignement, agent_cycles, map_contracts, contracts_variables, variable, variables_bounds):

    agent_cycles_to_satisfy = []
    agent_cycles_to_forget = []

    for cycle in agent_cycles:
        contracts = cycle[0][1] + cycle[1][1]
        nb_contract_to_instantiate=0
        check = False
        flexibility_recovered =0 # this line is important to add cycle satisfied by other in the set of satisfied cycles
        flexibility_to_recover = cycle[0][0] - cycle[1][0]

        for contract in contracts:
            source = contract.atoms[0].source.name
            dest = contract.atoms[0].dest.name
            l = contract.atoms[0].lowerBound
            if l < 0:  # if inverse contingent then l and u are inversed
                label = map_contracts[dest + "_" + source]
                contract_variable = contracts_variables[label]
            else:
                label = map_contracts[source + "_" + dest]
                contract_variable = contracts_variables[label]

            if contract_variable == variable: # this line is important to sort the set of cycles per variables
                check = True


            if contract_variable not in assignement: # if not in assignement I found another non assigned variable
                nb_contract_to_instantiate +=1
            else:  # the variable is assigned I checked how much I recovered
                variable_assignement = assignement[contract_variable]
                if contract in cycle[0][1]: # if in min path
                    if l<0: # if inverse contingent then l and u are inversed hence here u = l
                        bounds = variables_bounds[contract_variable]
                        flexibility_recovered += variable_assignement - bounds[0]

                    else: # not inverse hance u = u
                        bounds = variables_bounds[contract_variable]
                        flexibility_recovered += bounds[1] - variable_assignement

                else: # if in max path

                    if l < 0:  # if inverse contingent then l and u are inversed hence here l = u
                        bounds = variables_bounds[contract_variable]
                        flexibility_recovered += bounds[1] - variable_assignement

                    else:  # not inverse hance l = l
                        bounds = variables_bounds[contract_variable]
                        flexibility_recovered += variable_assignement - bounds[0]


        if check: # if the cycle concerns the variable

            if nb_contract_to_instantiate < 2 or flexibility_recovered >= flexibility_to_recover:
                agent_cycles_to_satisfy.append(cycle)
            else:
                agent_cycles_to_forget.append(cycle)





    return agent_cycles_to_satisfy, agent_cycles_to_forget


def compute_formula_to_forget(agent_cycles_to_forget, map_contracts,contracts_variables, variable):
    formula = []
    for cycle in agent_cycles_to_forget:

        min_p = cycle[0]
        max_p = cycle[1]

        flexibility = min_p[0] - max_p[0]

        for contract in min_p[1]:
            source = contract.atoms[0].source.name
            dest = contract.atoms[0].dest.name
            l = contract.atoms[0].lowerBound
            if l < 0:  # if inverse contingent then l and u are inversed
                label = map_contracts[dest + "_" + source]
                contract_variable = contracts_variables[label]
            else:
                label = map_contracts[source + "_" + dest]
                contract_variable = contracts_variables[label]

            if contract_variable == variable:
                cycle_formula = compute_min_path_formula([contract], map_contracts, contracts_variables)
                formula.append([Plus(cycle_formula), flexibility])

        for contract in max_p[1]:
            source = contract.atoms[0].source.name
            dest = contract.atoms[0].dest.name
            l = contract.atoms[0].lowerBound
            if l < 0:  # if inverse contingent then l and u are inversed
                label = map_contracts[dest + "_" + source]
                contract_variable = contracts_variables[label]
            else:
                label = map_contracts[source + "_" + dest]
                contract_variable = contracts_variables[label]

            if contract_variable == variable:
                cycle_formula = compute_max_path_formula([contract], map_contracts, contracts_variables)
                formula.append([Plus(cycle_formula), flexibility])

    return formula






def run_synchronous_backtracking(variables_bounds, agents_cycles, map_contracts, contracts_variables, rank, map_contracts_owner):

    assignement = {}
    current_rank = 0
    map_restriction = {}

    for variable in rank: # initialization

        map_restriction[variable] = []
    while (True):  # running backtracking



        if len(assignement) == len(rank):
            return assignement



        variable = rank[current_rank]


        owner = map_contracts_owner[str(variable)]
        agent_cycles = agents_cycles[owner]

        agent_cycles_to_satisfy, agent_cycles_to_forget = get_required_cycles(assignement, agent_cycles, map_contracts,
                                                                              contracts_variables, variable,
                                                                              variables_bounds)
        #print("to satisfy: ", agent_cycles_to_satisfy)
        #print("to forget: ", agent_cycles_to_forget)

        formula_to_satisfy = compute_agent_formula(agent_cycles_to_satisfy, map_contracts, contracts_variables)
        formula_to_forget = compute_formula_to_forget(agent_cycles_to_forget, map_contracts, contracts_variables,
                                                      variable)

        #print("formula to satisfy : ", formula_to_satisfy)
        #print("formula to forget : ", formula_to_forget)


        restrictions  = map_restriction[variable]
        variable_assignment = local_assignement(formula_to_satisfy, formula_to_forget, variables_bounds, variable, assignement, restrictions)
        #print("variable assignment ", variable, " = ",variable_assignment)

        if variable_assignment == None:

             if current_rank == 0:
                 return {}  # no solution exist

             else:
                 previous_variable = rank[current_rank - 1]
                 previous_variable_assignment = assignement[previous_variable]
                 map_restriction[previous_variable].append(Not(Equals(previous_variable, Int(previous_variable_assignment)))) # adding restriction
                 del assignement[previous_variable]


                 restrictions.clear() # remove all restriction
                 current_rank -=1


        else:
            assignement[variable] = variable_assignment
            #print("assignement ", assignement)
            current_rank +=1





