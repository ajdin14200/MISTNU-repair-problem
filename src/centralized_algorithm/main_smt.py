import copy
import itertools

from pysmt.shortcuts import *
from pysmt.typing import *

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


def encoding_requirements(network, controllables, contingent_durations, chain_formulas_map):

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

    formula = encoding_requirements(network, controllables, contingent_durations, chain_formulas_map)
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


def encode_secondary_objective(original_bounds, bounds):
    perc_constraints = []
    # Add "Swedish" fairness constraints to the formula
    ps = []
    for name, lst in bounds.items():
        assert len(lst) == 1, "Disjunctive contingent are not supported yet"
        (L, U) = lst[0]
        ps.append(p(name))
        orig_L, orig_U = original_bounds[name][0]
        perc_formula = Div(Plus(Minus(L, Real(orig_L)), Minus(Real(orig_U), U)), Real(orig_U - orig_L))
        not_touch_formula = And(Equals(Real(orig_L), L), Equals(Real(orig_U), U))
        p_formula = Equals(p(name), perc_formula)
        print("p ", p_formula.serialize())
        perc_constraints.append(p_formula)
        perc_constraints.append(GE(p(name), Real(0)))
    return And(perc_constraints), ps
            


def onbounds(mistnu, solver_name, use_secondary=False):
    contract_formula, bounds = encode_process(mistnu.B)
    print(contract_formula, bounds)
    p_formula = True
    P = []

    problems_formula = []
    for agent, network in zip(mistnu.agents, mistnu.networks):
        new_network = owned_contract_as_contingent(network)  # I transform all contract as contingent for checking WC
        formula= encode_network(new_network, bounds)
        problems_formula.append(formula)


    if use_secondary:
        p_formula, P = encode_secondary_objective(mistnu.B, bounds)
        formula = And(problems_formula + [contract_formula] + [p_formula])
    else:
        formula = And(problems_formula + [contract_formula])

    print(formula.serialize())
    objective = primary_objective(mistnu.B, bounds)
    obj1 = MinimizationGoal(objective)
    #print("P ", P)

    if use_secondary:
        tot = []
        if len(P) > 1:
            for p1 in P:
                for p2 in P:
                    if p1 != p2:
                        tot.append(Ite(Equals(p1, p2), Real(1), Real(0)))
            obj2 = MaximizationGoal(Plus(tot))

    with Optimizer(name=solver_name) as opt:
        opt.add_assertion(formula)
        if (not use_secondary) or len(P) == 1:
            result = opt.optimize(obj1)
        else:
            result = opt.lexicographic_optimize([obj1, obj2])

        if result is None:
            raise RuntimeError("The problem is not repairable!")
        else:
            model, cost = result
            bool = False
            if model:
                bool = True
            print(f"cost: {cost}")
            print(f"model: {model}")
            print("")
            res = {n: [(model.get_py_value(l), model.get_py_value(u)) for (l, u) in lst] for n, lst in bounds.items()}

            p_res = {}
            if use_secondary:
                p_res = {n: model.get_py_value(Symbol(f"{n}", REAL)) for n in bounds}


            return bool,res, p_res, mistnu.B
