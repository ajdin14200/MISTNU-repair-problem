
import os.path
from wc_checking_algorithm import *

from pysmt.shortcuts import *
from pysmt.optimization.goal import MaximizationGoal, MinimizationGoal

from structures import *


def diff(name):
    return Symbol(f"diff_{name}", REAL)


def lb(name):
    return Symbol(f"diff_{name}_LB", REAL)


def ub(name):
    return Symbol(f"diff_{name}_UB", REAL)


def p(name):
    return Symbol(f"p_{name}", REAL)

# We transform each cSTNU (one per agent) to an STNU by replacing each label on edges by the actual duration of the contract
def cSTNU_to_STNU(problem, B, map_contracts):


    constraints = set()
    for constraint in problem.constraints:
        if constraint.process:

            source = constraint.atoms[0].source
            dest = constraint.atoms[0].dest
            l = B[constraint.atoms[0].lowerBound][0][0]
            u =  B[constraint.atoms[0].upperBound][0][1]
            map_contracts[source.name+"_"+dest.name] = constraint.atoms[0].lowerBound
            at = AtomicConstraint(source,dest,l,u)
            atoms = set()
            atoms.add(at)
            new_constraint = Constraint(atoms, True, constraint.process, constraint.fixBinary())
            constraints.add(new_constraint)

        else:
            constraints.add(constraint)

    new_problem = Problem()
    new_problem.timePoints = problem.timePoints
    new_problem.constraints = constraints
    new_problem.contingent_parent  = problem.contingent_parent
    new_problem.vz = problem.vz
    new_problem.positive = problem.positive
    new_problem.disjunctivity = problem.disjunctivity
    new_problem.game = problem.game
    return new_problem

# This function check the Weak Controllability (WC) of each network (STNU)
# It is based on the latest most efficient algorithm for checking WC from Ajdin Sumic and Thierry Vidal 2024
# This new WC checking algorithm returns for an STNU its negative cycle if not weakly controllable
# Please note that each cycle is compose of a min and a max path where the min representive the positive path in the negative cycle from v_i to v_j
# while the max path the negative path in the negative cycle from v_j to v_i. This is due to the way the search is done in the WC-Checking algorithm
def compute_controllability(mas):
    agent_cycles = {}
    map_contracts = {}
    for i in range (len(mas.problems)):
        problem = cSTNU_to_STNU(mas.problems[i], mas.B, map_contracts)
        cycles = check_weak(problem)
        agent_cycles[mas.agents[i].name] = cycles
    return agent_cycles, map_contracts

# encode the contract (process) in the min path of the negative cycle
def compute_min_path_formula(path, map_contracts,contracts_variables, variables, cycle_variables):
    sum = []
    for contingent in path[1]:
        if contingent.process:
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
        if contingent.process:
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

        variable_formula = []
        for i, (L, U) in enumerate(bounds):
            LB = contract_variables[label][i][0]
            UB = contract_variables[label][i][1]
            bounds_formula = []

            if LB in variables and UB in variables:
                bounds_formula.append(GE(LB,Real(L)))
                bounds_formula.append(GE(UB,LB))
                bounds_formula.append(GE(Real(U),UB))

            else:

                if LB in variable_formula:
                    bounds_formula.append(GE(LB, Real(L)))
                    bounds_formula.append(GE(Real(U), LB))
                    bounds_formula.append(Equals(UB, Real(U)))

                else:
                    bounds_formula.append(GE(UB, Real(L)))
                    bounds_formula.append(GE(Real(U), UB))
                    bounds_formula.append(Equals(LB,Real(L)))

            variable_formula.append(And(bounds_formula))
        variables_formula.append(Or(variable_formula))
    return And(variables_formula)

# This function is the optimization function that minimizes the reduction of the bounds of the contracts
def primary_objective(original_bounds, bounds):
    s = []

    for n, lst in bounds.items():
        for i, (l, u) in enumerate(lst):
            L, U = original_bounds[n][i]
            s.append(Plus(Minus(Real(U), u), Minus(l, Real(L))))
    return Plus(s)

# This function is the optimization function that maximizes the number of contracts that are reduce by the same amount
def encode_secondary_objective(original_bounds, bounds):
    perc_constraints = []
    ps = []
    for name, lst in bounds.items():
        assert len(lst) == 1, "Disjunctive contingent are not supported yet"
        (L, U) = lst[0]
        ps.append(p(name))
        orig_L, orig_U = original_bounds[name][0]
        perc_formula = Div(Plus(Minus(L, Real(orig_L)), Minus(Real(orig_U), U)), Real(orig_U - orig_L))
        p_formula = Equals(p(name), perc_formula)
        perc_constraints.append(p_formula)
        perc_constraints.append(GE(p(name), Real(0)))
    return And(perc_constraints), ps

# This function is the centralized algorithm that repairs all the negative cycles using z3 as a solver
def repair_cycle(mas, solver='z3', use_secondary= False):
    agent_cycles, map_contracts = compute_controllability(mas)  # I get all the inconsistent cycles
    contract_variables = create_contracts_variables(mas.B) # I create a variable for each bound of each contract
    all_cycles_formula, variables = get_agents_formulas(agent_cycles, map_contracts, contract_variables) # I encode all the inconsistent cycle
    variables_formula = get_variables_formula(mas.B, variables, contract_variables) # I encode the variables

    P = [] # only used for fairness
    if use_secondary:
        p_formula, P = encode_secondary_objective(mas.B, contract_variables)
        formula = And(all_cycles_formula, And(variables_formula, p_formula))
    else:
        formula = And(all_cycles_formula, variables_formula)

    objective = primary_objective(mas.B, contract_variables)
    obj1 = MinimizationGoal(objective)

    if use_secondary:
        #print("P ", P)
        tot = []
        if len(P) > 1:
            for p1 in P:
                for p2 in P:
                    if p1 != p2:
                        tot.append(Ite(Equals(p1, p2), Real(1), Real(0)))
            obj2 = MaximizationGoal(Plus(tot))

    with Optimizer(name=solver) as opt:
        opt.add_assertion(formula)
        if (not use_secondary) or len(P) == 1:
            result = opt.optimize(obj1)
        else:
            result = opt.lexicographic_optimize([obj1, obj2])

        if result is None:
            return False, None, None, None
        else:
            model, cost = result

            res = {n: [(model.get_py_value(l), model.get_py_value(u)) for (l, u) in lst] for n, lst in contract_variables.items()}

            p_res = {}
            if use_secondary:
                p_res = {n: model.get_py_value(p(n)) for n in contract_variables}


            return True, res, p_res, mas.B



def repair_cycle(mas, agent_cycles, map_contracts , solver='z3', use_secondary= False):

    contract_variables = create_contracts_variables(mas.B) # I create a variable for each bound of each contract
    all_cycles_formula, variables = get_agents_formulas(agent_cycles, map_contracts, contract_variables) # I encode all the inconsistent cycle
    variables_formula = get_variables_formula(mas.B, variables, contract_variables) # I encode the variables

    P = [] # only used for fairness
    if use_secondary:
        p_formula, P = encode_secondary_objective(mas.B, contract_variables)
        formula = And(all_cycles_formula, And(variables_formula, p_formula))
    else:
        formula = And(all_cycles_formula, variables_formula)

    #print(formula.serialize())
    objective = primary_objective(mas.B, contract_variables)
    obj1 = MinimizationGoal(objective)

    if use_secondary:
        #print("P ", P)
        tot = []
        if len(P) > 1:
            for p1 in P:
                for p2 in P:
                    if p1 != p2:
                        tot.append(Ite(Equals(p1, p2), Real(1), Real(0)))
            obj2 = MaximizationGoal(Plus(tot))

    with Optimizer(name=solver) as opt:
        opt.add_assertion(formula)
        if (not use_secondary) or len(P) == 1:
            result = opt.optimize(obj1)
        else:
            result = opt.lexicographic_optimize([obj1, obj2])

        if result is None:
            return False, None, None, None
        else:
            model, cost = result

            #print(f"cost: {cost}")
            #print(f"model: {model}")
            #print("")
            #print('a solution exist to the repair problem of this MISTNU')
            res = {n: [(model.get_py_value(l), model.get_py_value(u)) for (l, u) in lst] for n, lst in contract_variables.items()}

            p_res = {}
            if use_secondary:
                p_res = {n: model.get_py_value(p(n)) for n in contract_variables}


            return True, res, p_res, mas.B









if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Encoder for controllability of temporal problems')


    parser.add_argument('inputFile', metavar='inputFile', type=str, help='The probmem to encode')
    parser.add_argument('--fairness', '-f', action="store_true")
    args = parser.parse_args()


    mas = MAS()
    mas.fromFile(args.inputFile)

    print('looking for cycles')
    start_time = time.time()
    agent_cycles, map_contracts = compute_controllability(mas)  # I get all the inconsistent cycles
    end_time = time.time()
    print('repairing cycles')
    print('time to find cycles : ', end_time-start_time)

    res_bool, res, p_res, original_bounds = repair_cycle(mas, agent_cycles, map_contracts, args.solver, use_secondary=args.fairness)  # get the projection for a negative cycle

    print("Repaired bounds:")

    for n, lst in res.items():
        for i, (l, u) in enumerate(lst):
            print(
                f"  {n}: original bounds -> {original_bounds[n][i]} new bounds -> [{l}, {u}] (~= [{float(l):.2f}, {float(u):.2f}])")
    print("")

    if args.fairness:
        print("Percentages:")
        for n, v in p_res.items():
            print(f"  p of {n}: {v} (~= {float(v):.2f})")







