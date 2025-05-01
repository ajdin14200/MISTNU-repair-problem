# Exceptions

class RedefinitionError(Exception):
    pass

class NoSuchElementError(Exception):
    pass


class MalformationError(Exception):
    pass


class ParsingError(Exception):

    def __init__(self, message="Parsing error", line=None):
        self.message = message
        self.line = line
        return

    def getMessage(self):
        res = self.message

        if self.message != None:
            res = res + " at line " + str(self.line)

        return res

    def __str__(self):
        return self.getMessage()

    pass


