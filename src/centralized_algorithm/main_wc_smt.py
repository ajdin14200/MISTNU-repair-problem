import argparse
import itertools
import os.path
import sys

sys.path.append(os.path.join(os.path.dirname(sys.argv[0]), "lib"))
sys.setrecursionlimit(100000)

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

# This function encodes the contracts
def encode_gamma(problem, bounds, agent):
    gamma = []
    uncontrollable_formulae = {}
    contingents = {}
    y = {}
    x = set()
    for c in problem.constraints:
        if c.contingent:
            assert c.isBinary()

            s = c.atoms[0].source
            d = c.atoms[0].dest

            label = d.name + "_" + agent.name

            fv = diff(label)

            y[label] = fv

            disj = []

            contingents[label] = []

            for i, a in enumerate(c.atoms):
                s = a.source
                l = a.lowerBound
                u = a.upperBound

                if (s.controllable):
                    vs = Symbol(s.name + "_" + agent.name, REAL)
                    x.add(vs)
                    uncontrollable_formulae[d] = Plus(vs, fv)
                else:
                    p = s
                    acc = []
                    op = d
                    while not p.controllable:
                        op_label = op.name + "_" + agent.name
                        acc.append(diff(op_label))
                        op = p
                        p = problem.contingent_parent[p]
                    op_label = op.name + "_" + agent.name
                    acc.append(diff(op_label))
                    vp = Symbol(p.name + "_" + agent.name, REAL)
                    x.add(vp)
                    uncontrollable_formulae[d] = Plus([vp] + acc)

                if c.process:
                    LB = bounds[l][i][0]
                    UB = bounds[l][i][1]
                    contingents[label].append([LB, UB])

                    disj.append(And([GE(fv, LB), LE(fv, UB)]))  # I change the constraint
                else:
                    disj.append(And([GE(fv, Real(l)), LE(fv, Real(u))]))  # I change the constraint
                    contingents[label].append([Real(l), Real(u)])

            gamma.append(Or(disj))
    return And(gamma), contingents, y, uncontrollable_formulae, x

# This function encodes the requirement/private constraints
def encode_psi(problem, uncontrollable_formulae, x, bounds, agent):
    frees = []
    for c in problem.constraints:
        if not c.contingent:
            disj = []
            for i, a in enumerate(c.atoms):
                s = a.source
                d = a.dest
                l = a.lowerBound
                u = a.upperBound

                if s.controllable:
                    vs = Symbol(s.name + "_" + agent.name, REAL)
                    x.add(vs)
                else:
                    vs = uncontrollable_formulae[s]

                if d.controllable:
                    vd = Symbol(d.name + "_" + agent.name, REAL)
                    x.add(vd)
                else:
                    vd = uncontrollable_formulae[d]

                conj = []
                if c.process:
                    LB = bounds[l][i][0]
                    UB = bounds[l][i][1]
                    conj.append(GE(Minus(vd, vs), LB))
                    conj.append(LE(Minus(vd, vs), UB))


                else:
                    if l != "-inf":
                        conj.append(GE(Minus(vd, vs), Real(l)))
                    if u != "+inf":
                        conj.append(LE(Minus(vd, vs), Real(u)))

                disj.append(And(conj))
            frees.append(Or(disj))
    return And(frees), list(x)


def my_product(bounds):
    for t in itertools.product(*[v[0] for v in bounds.values()]):
        yield dict(zip((diff(x) for x in bounds.keys()), t))


def primary_objective(original_bounds, bounds):
    s = []
    for n, lst in bounds.items():
        for i, (l, u) in enumerate(lst):
            L, U = original_bounds[n][i]
            s.append(Plus(Minus(Real(U), u), Minus(l, Real(L))))
    return Plus(s)


def encode_bound_constraints(original_bounds, bounds):
    bound_constraints = []
    for name, lst in bounds.items():
        for i, (L, U) in enumerate(lst):
            orig_L, orig_U = original_bounds[name][i]

            bound_constraints.append(GE(L, Real(orig_L)))
            bound_constraints.append(GE(U, L))
            bound_constraints.append(GE(Real(orig_U), U))
    return bound_constraints


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



def encode_on_bounds(problem, bounds, agent, use_secondary=False):
    gamma, contingents, y, uncontrollable_formulae, xp = encode_gamma(problem, bounds, agent)
    psi, x = encode_psi(problem, uncontrollable_formulae, xp, bounds, agent)

    all_consistencies = []
    for m in my_product(contingents):

        tmp_controllables = [FreshSymbol(REAL) for _ in x]
        m.update(zip(x, tmp_controllables))
        all_consistencies.append(psi.substitute(m))

    formula = And(all_consistencies)

    return formula, x


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


def owned_contract_as_contingent(problem):
    print(problem)
    for constraint in problem.constraints:
        if constraint.process == True and constraint.contingent == False:
            constraint.contingent = True
    exit(0)


def max_bounds(mas, SMT_solver, use_secondary=False):
    contract_formula, bounds = encode_process(mas.B)
    P = []

    problems_formulae = []
    for agent, problem in zip(mas.agents, mas.problems):

        owned_contract_as_contingent(problem)  # I transform all contract as contingent for checking WC


        formula, x = encode_on_bounds(problem, bounds, agent,use_secondary=False)
        print(formula.serialize())
        print("**************")
        problems_formulae.append(formula)

    if use_secondary:
        p_formula, P = encode_secondary_objective(mas.B, bounds)
        final_formula = And(problems_formulae + [contract_formula] + [p_formula])
    else:
        final_formula = And(problems_formulae + [contract_formula])
        print(formula.serialize())

    objective = primary_objective(mas.B, bounds)
    obj1 = MinimizationGoal(objective)

    if use_secondary:
        tot = []
        if len(P) > 1:
            for p1 in P:
                for p2 in P:
                    if p1 != p2:
                        tot.append(Ite(Equals(p1, p2), Real(1), Real(0)))
            obj2 = MaximizationGoal(Plus(tot))

    with Optimizer(name=SMT_solver) as opt:
        opt.add_assertion(final_formula)
        if (not use_secondary) or len(P) == 1:
            result = opt.optimize(obj1)
        else:
            result = opt.lexicographic_optimize([obj1, obj2])

        if result is None:
            raise RuntimeError("The problem is not repairable!")
            return False, None, None, None  # used for testing all benchmark

        else:
            model, cost = result

            res = {n: [(model.get_py_value(l), model.get_py_value(u)) for (l, u) in lst] for n, lst in bounds.items()}

            p_res = {}
            if use_secondary:
                p_res = {n: model.get_py_value(p(n)) for n in bounds}

            return True,res, p_res, mas.B
