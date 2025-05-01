# Problem structures
import math
import sys

from errors import *



class TimePoint(object):

    def __init__(self, name, controllable):
        self.name = name
        self.controllable = controllable
        return

    pass



class AtomicConstraint(object):

    def __init__(self, source, dest, lower, upper):

        if self.checkValue(lower, False) and self.checkValue(upper, True):
            self.source = source
            self.dest = dest
            self.lowerBound = lower
            self.upperBound = upper
        else:
            raise MalformationError()

        return


    def checkValue(self, v, upper):
        if isinstance(v, str):
            if 'inf' not in v:
                return True
            else:
                return (upper and (v == "+inf")) or \
                    ((not upper) and (v == "-inf"))
        else:
            return isinstance(v, float) or isinstance(v, int)

        assert False
        return False

    def __str__(self):
        return ("(%s - %s) in [%s, %s]" % \
                    (self.dest.name, self.source.name,
                     str(self.lowerBound), str(self.upperBound)))

    pass

class Agent(object):
    def __init__(self, name):
        self.name  = name

# This class represent the MISTNU class
class MISTNU(object):

    def __init__(self):
        self.agents = []    # A is a set of agent
        self.networks = []   # S a set if temporal network
        self.B = {}          # B the map of contract to bound
        self.readers = {}    # R a map of agent to a list of contracts it reads
        self.owners = {}    # O a map of agent to a list of contracts it write

    def encode_tn_from_file(self, entries, pointer, tn, agent_contract, agent):

        nn = int(entries[pointer])  # number of timepoints
        ne = int(entries[pointer+1]) # number of constraints
        label = None
        pointer = pointer + 2
        for i in range(0, nn): # for each timepoint I create an instance of TimePoint
            name = entries[pointer]  # get name
            cflag = entries[pointer + 1]  # get type

            tn.createTimePoint(name, (cflag == "c"))
            pointer = pointer + 2 # new line

        for i in range(0, ne): # for each constraint I create an instance of Constraint
            ndisjunction = int(entries[pointer]) # the first number is for disjunctivity

            cflag = entries[pointer + 1] # type of constraints
            contingent = (cflag == "c") # is contingent ?
            contract = False

            pointer = pointer + 2

            atoms = set()
            for _ in range(0, ndisjunction): # for each intervals, here only one for STNUs
                s = tn.getTimePoint(entries[pointer])
                d = tn.getTimePoint(entries[pointer + 1])

                l = entries[pointer + 2]
                u = entries[pointer + 3]



                try:
                    if u in self.B and l in self.B: # if is a contract
                        contract = True
                        label = u
                    else:
                        if u != "+inf" and u != "-inf":
                            #u = float(u)
                            u = int(u)

                        if l != "+inf" and l != "-inf":
                            #l = float(l)
                            l = int(l)
                except Exception:
                    raise ParsingError("Expected float number or infinity keywords", nn + i + 1)

                atom = None
                try:
                    atom = AtomicConstraint(s, d, l, u)
                except MalformationError:
                    raise

                if atom is not None:
                    atoms.add(atom)

                pointer = pointer + 4 # new line

            c = tn.createConstraint(atoms, contingent, contract)
            if contract:
                if agent_contract[label] == agent.name:
                    self.owners[agent_contract[label]].append(c)




        return pointer

    def fromFile(self, filename):
        f = open(filename, "rt")
        entries = f.read().split()
        agent_contract = {}
        number_agent = int(entries[0])
        for i in range(1, number_agent + 1): # get agents' name
            agent = Agent(entries[i])
            self.agents.append(agent)


        pointer = number_agent + 1  # next line
        number_contract = int(entries[pointer])  # get the number of contracts
        for i in range(1, number_contract + 1): # get name of contract
            self.B[entries[pointer + i]] = []
            self.readers[entries[pointer + i]] = []

        pointer = pointer + number_contract + 1  # next line
        for line in range(number_contract): # for each contract we get the bounds, the owner and the readers
            contract_label = entries[pointer]
            contract_bounds = [int(entries[pointer + 1]), int(entries[pointer + 2])]
            contract_owner = entries[pointer + 4]
            number_readers = int(entries[pointer + 5])
            contract_readers = []
            pointer = pointer + 5
            self.owners[contract_owner] = []
            agent_contract[contract_label] = contract_owner
            for reader in range(1, number_readers + 1):
                contract_readers.append(entries[pointer + reader])
            self.B[contract_label].append(contract_bounds)
            self.readers[contract_label] = contract_readers
            pointer = pointer + reader + 1

        for i in range(number_agent): # for each agent we encode its network
            tn = Network()
            agent = self.agents[i]
            pointer = self.encode_tn_from_file(entries, pointer, tn, agent_contract, agent)
            self.networks.append(tn)



class Constraint(object):

    def __init__(self, atoms, contingent=False, contract=False, fixBin=False):
        self.atoms = list(atoms)
        self.contingent = contingent
        self.contract = contract # this will help in recognizing a constraint which is a contract

        if fixBin and len(atoms) > 1:
            self.fixBinary()

        return

    def isBinary(self):
        s = None
        d = None

        for a in self.atoms:
            if s is None and d is None:
                s = a.source
                d = a.dest
                assert s is not None
                assert d is not None
            else:
                if a.source != s or a.dest != d:
                    return False

        return True


    def fixBinary(self):
        s = None
        d = None

        for a in self.atoms:
            if s is None and d is None:
                s = a.source
                d = a.dest
                assert s is not None
                assert d is not None
            else:
                if a.source == d and a.dest == s:
                    tmp = a.source
                    a.source = a.dest
                    a.dest = tmp

                    l = a.lowerBound
                    u = a.upperBound

                    if l != 0 and u != 0:
                        if l == -math.inf:
                            a.upperBound = math.inf
                        else:
                            a.upperBound = -1 * l

                            if u == math.inf:
                                a.lowerBound = -math.inf
                            else:
                                a.lowerBound = -1 * u
        return

    pass





class Network(object):

    def __init__(self):
        self.timePoints = {}
        self.constraints = set()
        self.contingent_parent = {}
        self.vz = None


        return


    def createTimePoint(self, name, controllable):
        if not controllable:
            self.game = True

        if type(name) is int:
            name = ("X%d" % name)

        if name in self.timePoints:
            raise RedefinitionError()

        n = TimePoint(name, controllable)
        if len(self.timePoints) == 0:
            self.vz = n
        self.timePoints[name] = n

        return n


    def getTimePoint(self, name):
        if type(name) is int:
            name = ("X%d" % name)

        if name in self.timePoints:
            return self.timePoints[name]
        raise NoSuchElementError()


    def createConstraint(self, atoms, contingent=False, contract=False, fixBinary=False):
        assert len(atoms) > 0;
        c = Constraint(atoms, contingent, contract, fixBinary)
        self.constraints.add(c)

        if c.contingent:
            s = c.atoms[0].source
            d = c.atoms[0].dest
            self.contingent_parent[d] = s

        return c
