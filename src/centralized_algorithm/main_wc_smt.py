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
    print("bounds ", bounds)
    print(original_bounds)
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


def encode_quantified(problem, controllability="weak", solver_name="z3", use_secondary=False):
    gamma, y, uncontrollable_formulae, bounds, original_bounds, xp = encode_gamma(problem)
    psi, x = encode_psi(problem, uncontrollable_formulae, xp)

    if controllability == "weak":  # if I check weak controllability
        alpha = Exists(x, psi)
        beta = ForAll(y.values(), Implies(gamma, alpha))

    else:
        alpha = ForAll(y.values(), Implies(gamma, psi))
        # beta = Exists(x, alpha)
        beta = alpha

    optimization_obj = primary_objective(original_bounds, bounds)

    formula = qelim(beta, solver_name=solver_name)
    formula = And(formula, And(encode_bound_constraints(original_bounds, bounds)))

    ps = None
    if use_secondary:
        perc_constraints, ps = encode_secondary_objective(original_bounds, bounds)
        formula = And(formula, And(perc_constraints))

    return formula, optimization_obj, ps, bounds, original_bounds


def encode_on_bounds(problem, bounds, original_bounds, agent, controllability="weak", use_secondary=False):
    gamma, contingents, y, uncontrollable_formulae, xp = encode_gamma(problem, bounds, agent)
    psi, x = encode_psi(problem, uncontrollable_formulae, xp, bounds, agent)

    all_consistencies = []
    for m in my_product(contingents):
        if controllability == "weak":
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
    for constraint in problem.constraints:
        if constraint.process == True and constraint.contingent == False:
            constraint.contingent = True


def max_bounds(mas, solver_name="z3", controllability="weak", type="onbounds", use_secondary=False):
    contract_formula, bounds = encode_process(mas.B)
    p_formula = True
    P = []

    problems_formulae = []
    for agent, problem in zip(mas.agents, mas.problems):
        if controllability == "weak":
            owned_contract_as_contingent(problem)  # I transform all contract as contingent for checking WC

        if type == "onbounds":
            formula, x = encode_on_bounds(problem, bounds, mas.B, agent, controllability=controllability,
                                          use_secondary=False)
        else:
            formula, bounds, original_bounds = encode_quantified(mas, controllability=controllability, solver_name="z3")
        problems_formulae.append(formula)

    if use_secondary:
        p_formula, P = encode_secondary_objective(mas.B, bounds)
        formula = And(problems_formulae + [contract_formula] + [p_formula])
    else:
        formula = And(problems_formulae + [contract_formula])

    print(formula.serialize())
    objective = primary_objective(mas.B, bounds)
    obj1 = MinimizationGoal(objective)
    print("P ", P)

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

            print(f"cost: {cost}")
            print(f"model: {model}")
            print("")
            res = {n: [(model.get_py_value(l), model.get_py_value(u)) for (l, u) in lst] for n, lst in bounds.items()}

            p_res = {}
            if use_secondary:
                p_res = {n: model.get_py_value(p(n)) for n in bounds}

            if controllability == "strong" and type == "bound":
                print("Consistent Schedule:")
                for n in x:
                    print(f"  {n}: {model.get_py_value(n)} ")
                print("")

            return res, p_res, mas.B


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Encoder for controllability of temporal problems')

    parser.add_argument('controllability', metavar='controllability', type=str, choices=["weak"],
                        help='which type of controllability to check')
    parser.add_argument('type', metavar='type', type=str, choices=["onbounds", "quantified"],
                        help='which type of algorithm to use')
    parser.add_argument('inputFile', metavar='inputFile', type=str, help='The problem to encode')
    parser.add_argument('--solver', '-s', type=str, help='Which solver to use', default=None)
    parser.add_argument('--qelim', '-q', type=str, help='Which qelim to use', default=None)
    parser.add_argument('--fairness', '-f', action="store_true")
    args = parser.parse_args()

    # Main script
    mas = MAS()
    mas.fromFile(args.inputFile)
    print(mas.B)

    res, p_res, original_bounds = max_bounds(mas, args.solver,
                                             controllability=args.controllability,
                                             type=args.type,
                                             use_secondary=args.fairness)  # get the projection for a negative cycle

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