from typing import List

import cvxpy as cp
from cvxpy import *
from cvxpy.constraints.constraint import *
from numpy.core.multiarray import ndarray

from abc import ABC



#from eoscsp.mapping import Mapping


class GeneralFormConsensusOptimizationProblem:
    """
    A class representing a General Form Consensus Optimization Problem.
    """

    def __init__(self, variables: List[Variable], costs: List[ndarray], constraints: List[List[Constraint]],
                 mapping, c_cent: ndarray = None, a_cent: ndarray = None, b_cent: ndarray = None):
        """
        Creates a GFCOP instance.

        :type variables: List[Variable]
        :param variables: the list of variables for each proximal LP i
        :type costs: List[ndarray]
        :param costs: the list of costs for each proximal LP i
        :type constraints: List[List[Constraint]]
        :param constraints: the list of list of constraint for each proximal LP
        :type mapping: Mapping
        :param mapping: the G mapping to specify which components are considered for consensus
        :type c_cent: nbarray
        :param c_cent: the cost matrix for a centralized LP
        :type a_cent: ndarray
        :param a_cent: the coefficient matrix for a centralized LP
        :type b_cent: ndarray
        :param b_cent: the bound matrix for a centralized LP
        """
        self.variables = variables
        self.costs = costs
        self.constraints = constraints
        self.mapping =mapping
        self.c_cent = c_cent
        self.b_cent = b_cent
        self.a_cent = a_cent

    @property
    def nb_agents(self) -> int:
        """
        :rtype: int
        :return: the number of agents in the consensus problem (excluding the master)
        """
        return len(self.variables)

    @property
    def get_max_nb_vars(self) -> int:
        """
        :rtype: int
        :return: the maximum number of variable components among all agents
        """
        return max([self.get_nb_vars(i) for i in range(self.nb_agents)])

    def get_nb_vars(self, i: int) -> int:
        """
        :type i: int
        :param i: the agent number
        :rtype: int
        :return: the number of variable components owned by the agent i
        """
        if i > self.nb_agents:
            raise ValueError("i parameter must be lower than the number of agents: " + str(self.nb_agents))
        return len(self.costs[i])


def compute_min_path_formula(contracts, map_contracts,contracts_variables):
    sum = []
    for contingent in contracts:
        if contingent.contract:
            source = contingent.atoms[0].source.name
            dest = contingent.atoms[0].dest.name
            l = contingent.atoms[0].lowerBound
            u = contingent.atoms[0].upperBound

            if l<0: # if inverse contingent then l and u are inversed
                contract_variable = contracts_variables[map_contracts[dest+"_"+source]][0]
                sum.append(contract_variable - (u*-1))


            else:
                contract_variable = contracts_variables[map_contracts[source+"_"+dest]][1]
                sum.append(u - contract_variable)

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
                contract_variable = contracts_variables[map_contracts[dest+"_"+source]][1]
                sum.append((l*-1) - contract_variable)



            else:
                contract_variable = contracts_variables[map_contracts[source+"_"+dest]][0]
                sum.append(contract_variable - l)


    return sum


def compute_cycle_formula(cycle, map_contracts,contracts_variables):
    min_p = cycle[0]
    max_p = cycle[1]

    flexibility = min_p[0] - max_p[0]

    # min_path
    min_formula = compute_min_path_formula(min_p[1], map_contracts,contracts_variables)
    max_formula = compute_max_path_formula(max_p[1], map_contracts,contracts_variables)
    sum_cycle = sum(min_formula + max_formula)
    return sum_cycle >= flexibility


def compute_agent_cycles_constraint(cycles, map_contracts,contracts_variables):
    # here we need to identify the constraint that are alone to prune the domain
    constraints = []
    for cycle in cycles:
        cycle_formula= compute_cycle_formula(cycle, map_contracts,contracts_variables)
        constraints.append(cycle_formula)


    return constraints  # I return the formula itself


def create_variables(mistnu):
    contract_variables = {}
    map_contract_owner = {}

    for agent, contracts in mistnu.owners.items():
        map_contract_owner[agent] = []
        for contract in contracts:

                name = contract.atoms[0].lowerBound
                var_l = Variable(name= name+"_l")
                var_u = Variable(name= name+"_u")
                contract_variables[name] = [var_l, var_u]
                map_contract_owner[agent].append((var_l,var_u)) # add the tuple (l,u) for the variable
    return contract_variables, map_contract_owner

def create_map_contracts_owners(owners):
    map_contract_owner = {}
    for agent, contracts in owners.items():
        for contract in contracts:
            map_contract_owner[contract.atoms[0].lowerBound] = agent
    return  map_contract_owner
def get_agents_functions(map_contract_owner):
    functions = {}

    for agent, variables in map_contract_owner.items():

        sum_variables = 0
        for (l,u) in variables:

           sum_variables += u -l

        functions[agent] = sum_variables
    return functions

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


def get_variables_bounds(contract_variables, B):
    variables_bounds = {}
    for name, bounds in B.items():

        variable_tuple = contract_variables[name]
        variables_bounds[variable_tuple[0]] = bounds[0]
        variables_bounds[variable_tuple[1]] = bounds[0]

    return variables_bounds
def run_admm(mistnu, agent_cycles, map_contracts):

    #print("agent cycles", agent_cycles)
    map_contract_owner = create_map_contracts_owners(mistnu.owners)

    contract_variables, map_variables_owner = create_variables(mistnu)

    variables_bounds = get_variables_bounds(contract_variables, mistnu.B)
    # print(variables)
    # print(map_variables_owner)
    #print(variables_bounds)

    functions = get_agents_functions(map_variables_owner)
    print(functions)

    agent_cycles, list_involved_contract = share_cycle(agent_cycles, map_contracts, mistnu.readers, map_contract_owner)
    print(agent_cycles['A_0'])
    print(list_involved_contract)


    for agent, cycles in agent_cycles.items():
        print(compute_agent_cycles_constraint(cycles, map_contracts, contract_variables))


    nb_agents = len(mistnu.agents)
    proximal_solvers = []



    exit(0)


    nb_agents = len(mistnu.agents)
    proximal_solvers = []
    xs = [None] * nb_agents
    us = [None] * nb_agents
    hcs = [None] * nb_agents
    vs = [None] * nb_agents
    hs = [{}] * nb_agents
    inverse_mapping = self.gfcop.mapping.inverse
    dim = len(self.gfcop.costs[0])
    nb_messages = 0
    size_messages = 0
    times = {}



    exit(0)

    map_contract_owner = create_map_contracts_owners(mas.owners)


    contracts_variables, agent_variables, variables_bounds  = create_contracts_variables(mas.B, mas.owners)

    agent_cycles, list_involved_contract = share_cycle(agent_cycles, map_contracts, mas.readers, map_contract_owner)



    agent_shared_cycles, single_agent_cycles = sort_cycles(agent_cycles)
    set_variables_bounds(single_agent_cycles, mas.B, map_contracts, contracts_variables, variables_bounds)

    rank = compute_agent_ranking(agent_cycles, map_contracts, contracts_variables)


    assignement = run_synchronous_backtracking(variables_bounds, agent_cycles, map_contracts, contracts_variables, rank, map_contract_owner)
    print("No solution exist !!!!") if len(assignement) == 0 else print("A solution exist ! The solution is : ", assignement)
    return False if len(assignement) == 0 else True