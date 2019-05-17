from __lexer__ import *
from sys import *

class CodeGen:
    
    def __init__(self):
        self.code = ''
        self.lbli = 1

    def __call__(self, *a):
        self.code += '  ' + a[0] + ' ' + (', '.
        join([str(e) for e in a[1:]])) + '\n'
    
    def label(self, i = None):
        if i == True:
            pass
        elif i == None:
            self.code += 'lbl %d\n' % self.lbli
        else:
            self.code += 'lbl %d\n' % i
            return
        self.lbli += 1
        return self.lbli - 1

class Parser:

    def __init__(self):

        # create codegen
        self.asm = CodeGen()
        self.asm('stk 32')
        self.asm('org 0')

        # init memory
        self.meminit()

    def expr(self, expr, var_address=None):
        try:
           co = compile(expr, self.lnerr, 'eval')
        except SyntaxError as e:
           print(e.text)
           print((e.offset - 1) * ' ' + '^')
           exit('error: %s (%s)' % (e.msg.replace(
                'EOF', 'EOL'), self.lnerr))
        except Exception as e:
           exit('error: %s (%s)' % (e, self.lnerr))

        def op(instr):
            self.asm('pop', 'r2')
            self.asm('pop', 'r1')
            self.asm(instr, 'r1', 'r2')
            self.asm('psh', 'r1')

        for c1, c2 in zip(*[iter(list(co.co_code))] * 2):
            
            # load const
            if c1 == 100:
                c = co.co_consts[c2]
                if c == None:
                    self.asm('psh', 0)
                elif isinstance(c, int):
                    self.asm('psh', c)
                else:
                    exit('error: invalid const %s at `%s` (line %d)' % (
                        str(bytes(c.encode()))[1:], expr, self.ln_no))

            # load variable
            elif c1 == 101:
                self.asm('rcl', 'r1', self.addr(co.co_names[c2]))
                self.asm('psh', 'r1')
            
            # assign
            elif c1 == 83:
                if var_address != None:
                    self.asm('pop', 'r2')
                    self.asm('mov', 'r1', var_address)
                    self.asm('sto', 'r1', 'r2')

            elif c1 == 0x17 or c1 == 0x37: op('add')
            elif c1 == 0x18 or c1 == 0x38: op('sub')
            elif c1 == 0x14 or c1 == 0x39: op('mul')
            elif c1 == 0x15 or c1 == 0x1b or c1 == 0x3a: op('div')

            # compare op
            elif c1 == 107:

                cops = {
                    '<':  0,
                    '<=': 1,
                    '==': 2,
                    '!=': 3,
                    '>':  4,
                    '>=': 5,
                }

                if c2 == cops['==']:   op('eq_')
                elif c2 == cops['!=']: op('ne_')
                elif c2 == cops['<=']: op('le_')
                elif c2 == cops['>=']: op('ge_')
                elif c2 == cops['<']:  op('lt_')
                elif c2 == cops['>']:  op('gt_')
                else:
                    exit('error: unknown operator %d at `%s` (line %d)' % (
                        c2, expr, self.ln_no))
            
            # invalid expression
            else:
                exit('error: invalid expression `%s` (line %d)' % (
                    expr, self.ln_no))

    def meminit(self):
        # key: varname, value: address
        self.mem = {}
        # to determine address
        self.memi = 32
        # to determine the existence of var
        self.variables = []

    def addr(self, name):
        # function name + variable name
        f = self.func
        f = '' if f == None else f
        f = f + '.' + name
        
        # create if variable doesn't exist
        if f not in self.variables:
            self.variables += [f]
            self.mem[f] = self.memi
            self.memi += 1

        # return address of variable
        return self.mem[f]

    def get_indent(self, line):
        # remove spaces from right ' a ' -> ' a'
        rline = line.rstrip()
        # return rline with removed stripped line
        return rline.replace(line.strip(), '')

    def parse(self, code):
        
        # global
        self.func = None

        # (stmt, indent, ...)
        self.to_close = []

        for i, line in enumerate((code + '\n\n').splitlines()):
            
            self.ln_no = i + 1
            tokens = lex(line)
            lnerr = 'line %d' % self.ln_no
            self.lnerr = lnerr
            self.line = line

            if line.strip() != '' and tokens[0] == 'else':
                try:
                    tc = self.to_close.pop()
                except:
                    exit('error: `else` without `if` (%s)' % lnerr)

                # print(tc)

                self.asm.code += '\n'
                self.asm('; else')
                
                sklb = self.asm.label(i = True)
                
                self.asm('jmp', sklb)
                self.asm('lbl', tc[2])

                self.to_close += [('else', self.get_indent(line), sklb)]
                continue

            if len(self.to_close) > 0:
                tc = self.to_close[-1]
                if tc[1] == self.get_indent(line):
                    # print(tc, lnerr)

                    if tc[0] == 'else':
                        
                        self.asm.code += '\n'
                        self.asm('; end')
                        self.asm('lbl', tc[2])

                    if tc[0] == 'if':
                        self.asm.code += '\n'
                        self.asm('; end')
                        self.asm('lbl', tc[2])

                    if tc[0] == 'while':
                        self.asm.code += '\n'
                        self.asm('; end')
                        self.asm('jmp', tc[3])
                        self.asm('lbl', tc[2])

                    self.to_close.pop()

            if line.strip() == '':
                continue

            self.asm.code += '\n'
            self.asm('; ' + line.strip())

            # inline asm
            if tokens[0] == 'as':
                
                if tokens[1][0] != '"' or tokens[1][-1] != '"':
                    exit('error: expected string after `as` (%s)' % lnerr)
                
                self.asm(eval(tokens[1]))
            
            # if statement
            elif tokens[0] == 'if':
                
                cond = ' '.join(tokens[1:])
                self.expr(cond)
                sklb = self.asm.label(i = True)
                
                self.asm('pop', 'r1')
                self.asm('jz_', 'r1', sklb)
                
                self.to_close += [('if', self.get_indent(line), sklb)]
            
            # while statement
            elif tokens[0] == 'while':
                
                sklb = self.asm.label(i = True)
                back = self.asm.label(i = True)
                
                cond = ' '.join(tokens[1:])
                self.asm('lbl', back)
                self.expr(cond)
                
                self.asm('pop', 'r1')
                self.asm('jz_', 'r1', sklb)
                
                self.to_close += [('while', self.get_indent(line),
                    sklb, back)]

            # var assign
            elif len(tokens) > 1 and tokens[1] == '=':
                
                name = tokens[0]
                addr = self.addr(name)
                expr = ' '.join(tokens[2:])
                self.expr(expr, var_address=addr)

            # expr
            else:

                self.expr(' '.join(tokens))
                self.asm('pop', 'r1')

