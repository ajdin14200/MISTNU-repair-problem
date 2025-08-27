import copy
import itertools


from optimization_functions import *

from structures import *


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

            if controllability == "Strong" and constraint.contract:
                l,u = bounds[l][0] # This requirement constraint is a contract so the bounds are variables

            else:
                l,u = Real(l), Real(u)

            formula.append(GE(Minus(vd, vs), l))
            formula.append(LE(Minus(vd, vs), u))
    return And(formula)

def my_product(bounds):
    for t in itertools.product(*[v for v in bounds.values()]):
        yield dict(zip((Symbol(f"{x}",REAL) for x in bounds.keys()), t))

def encode_network(network, bounds, controllability):

    controllables, contingent_durations = get_timepoints_variables(network)
    parents_map = get_variables_parent(network) # get parent for chain of contingents
    chain_formulas_map = get_chain_formulas(parents_map, controllables, contingent_durations)  # encode chains of contracts:  Z -u-> C -v-> D, we have D = Z + u + v
    contingent_duration_bounds = get_variables_bounds(network, bounds) # for each contingent variable associate LB/UB variable if contract, else real bounds' value

    #print("controllables ", controllables)
    #print("contingent durations ", contingent_durations)
    #print("parent map ", parents_map)
    #print("chain formulas ",chain_formulas_map)
    #print("contingent duration bounds ",contingent_duration_bounds)
    #print("bounds ", bounds)

    formula = encoding_requirements(network, controllables, chain_formulas_map, controllability, bounds)
    #print("formula ", formula)
    projections_formula= []
    for m in my_product(contingent_duration_bounds):

        if controllability == "Weak":
            tmp_controllables = [FreshSymbol(REAL) for _ in controllables.values()]
            m.update(zip(controllables.values(), tmp_controllables))
        projections_formula.append(formula.substitute(m))

    #print("formula ",projections_formula)
    return And(projections_formula)


def onbounds(mistnu, solver_name, controllability, use_optim):
    contract_formula, bounds = encode_process(mistnu.B)
    #print(contract_formula, bounds)

    problems_formula = []
    for agent, network in zip(mistnu.agents, mistnu.networks):
        if controllability == "Weak":
            network = owned_contract_as_contingent(network)  # I transform all contract as contingent for checking WC
        formula= encode_network(network, bounds, controllability)
        problems_formula.append(formula)

    formula = And(problems_formula + [contract_formula])
    return run_optimization(mistnu, formula, bounds, use_optim, solver_name)
