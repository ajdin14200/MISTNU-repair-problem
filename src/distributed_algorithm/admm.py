from typing import List

from cvxpy import Variable
from cvxpy.constraints.constraint import Constraint
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


def create_variables(mistnu):
    print(mistnu.B)
    variables = []
    for name, contract in mistnu.B.items():
        for i, (l, u) in enumerate(contract):
            var_l = Variable(name= name+"_l"+"_"+str(i))
            var_u = Variable(name= name+"_u"+"_"+str(i))
            variables.append(var_l)
            variables.append(var_u)
    return variables


def run_admm(mistnu, agent_cycles, map_contracts):

    #print("agent cycles", agent_cycles)

    print(mistnu.owners)
    variables = create_variables(mistnu)
    print(variables)

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