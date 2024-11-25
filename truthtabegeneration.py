import re
import time
from dataclasses import dataclass
from typing import List, Dict, Union, Optional
from multiprocessing import Pool, cpu_count

start_time = time.time()

# Precompiled regular expression for performance
token_pattern = re.compile(r'\b(?:var|show|show_ones|not|and|or|True|False)\b|\w+|[()=;]')


@dataclass
class Node:
    type: str
    value: Optional[str] = None
    left: Optional['Node'] = None
    right: Optional['Node'] = None


def tokenize(text):
    try:
        text = ' '.join(line.split('#')[0].strip() for line in text.split('\n') if line.strip())
        return token_pattern.findall(text)
    except Exception as e:
        raise ValueError(f"Tokenization failed: {e}")


def tokenize(text):
    try:
        text = ' '.join(line.split('#')[0].strip() for line in text.split('\n') if line.strip())
        return token_pattern.findall(text)
    except Exception as e:
        raise ValueError(f"Tokenization failed: {e}")

def check_input_syntax(tokens):
    i = 0

    while i < len(tokens):
        if tokens[i] == 'var':
            i += 1
            # Check each variable declaration, no '=' allowed before the semicolon
            while i < len(tokens) and tokens[i] != ';':
                if tokens[i] == '=':
                    raise SyntaxError("Unexpected '=' found after 'var' declaration and before semicolon")
                i += 1

            if i >= len(tokens) or tokens[i] != ';':
                raise SyntaxError("Missing semicolon (;) after 'var' declaration")

            i += 1  # Skip the semicolon

        elif tokens[i] == 'show' or tokens[i] == 'show_ones':
            i += 1
            # Check that the show instruction is properly formatted and ends with a semicolon
            while i < len(tokens) and tokens[i] != ';':
                # If a 'var' declaration is found after a 'show' but before the semicolon, raise an error
                if tokens[i] == 'var':
                    raise SyntaxError("Unexpected 'var' declaration found after 'show' statement and before semicolon")
                i += 1

            if i >= len(tokens) or tokens[i] != ';':
                raise SyntaxError("Missing semicolon (;) after 'show' or 'show_ones' statement")

            i += 1  # Skip the semicolon

        else:
            # Handle assignments (which don't start with var/show/show_ones)
            variable = tokens[i]
            i += 1
            if i < len(tokens) and tokens[i] == '=':
                i += 1  # Skip '='
                # Now check until the semicolon
                while i < len(tokens) and tokens[i] != ';':
                    if tokens[i] == '=':
                        raise SyntaxError("Multiple '=' found before a semicolon")
                    # Check for show, show_ones, or var after '='
                    if tokens[i] in ['show', 'show_ones', 'var']:
                        raise SyntaxError(f"Unexpected '{tokens[i]}' found after '=' before semicolon")
                    i += 1
                
                if i == len(tokens) or tokens[i] != ';':
                    raise SyntaxError("Missing semicolon (;) after assignment")
                i += 1  # Skip the semicolon
            else:
                raise SyntaxError("Expected '=' in assignment")

    # Ensure there is a 'show' or 'show_ones' statement
    if 'show' not in tokens and 'show_ones' not in tokens:
        raise SyntaxError("Missing 'show' or 'show_ones' statement")
    
    # Check for semicolon after the last 'show' or 'show_ones'
    last_show_index = max(tokens.index('show') if 'show' in tokens else -1,
                          tokens.index('show_ones') if 'show_ones' in tokens else -1)
    if ';' not in tokens[last_show_index:]:
        raise SyntaxError("'show' or 'show_ones' statement must end with a semicolon (;)")



    
def parse_expression(tokens, start):
    current = [start]

    def parse_primary():
        if tokens[current[0]] == '(':
            current[0] += 1
            expr = parse_or()
            if tokens[current[0]] == ')':
                current[0] += 1
                return expr
            else:
                raise ValueError("Mismatched parentheses")
        elif tokens[current[0]] == 'not':
            current[0] += 1
            return Node('not', left=parse_primary())
        elif tokens[current[0]] in ['True', 'False']:
            node = Node('boolean', tokens[current[0]])
            current[0] += 1
            return node
        else:
            node = Node('variable', tokens[current[0]])
            current[0] += 1
            return node

    def parse_and():
        left = parse_primary()
        while current[0] < len(tokens) and tokens[current[0]] == 'and':
            current[0] += 1
            right = parse_primary()
            left = Node('and', left=left, right=right)
        return left

    def parse_or():
        left = parse_and()
        while current[0] < len(tokens) and tokens[current[0]] == 'or':
            current[0] += 1
            right = parse_and()
            left = Node('or', left=left, right=right)
        return left

    return parse_or()


def parse(tokens):
    try:
        all_variables = []  # Track all variables in order of declaration
        current_variables = []  # Track variables available at each point
        assignments = {}
        show_instructions = []
        current = 0

        while current < len(tokens):
            if tokens[current] == 'var':
                current += 1
                # Collect variables until semicolon
                new_vars = []
                while tokens[current] != ';':
                    if tokens[current] not in all_variables:
                        new_vars.append(tokens[current])
                    current += 1
                current += 1  # Skip semicolon
                
                # Add new variables to both tracking lists
                all_variables.extend(new_vars)
                current_variables.extend(new_vars)

                if len(all_variables) > 64:
                    raise ValueError("Too many variables declared. The limit is 64 variables.")

            elif tokens[current] in ['show', 'show_ones']:
                instruction_type = tokens[current]
                current += 1
                identifiers = []
                while tokens[current] != ';':
                    identifiers.append(tokens[current])
                    current += 1
                
                # Store the current state with this show instruction
                show_instructions.append({
                    'type': instruction_type,
                    'identifiers': identifiers,
                    'vars': current_variables.copy(),  # Copy current available variables
                    'assignments': {k: v for k, v in assignments.items()}  # Copy current assignments
                })
                current += 1
                
            elif '=' in tokens[current:]:
                variable = tokens[current]
                current += 2  # Skip variable and '='
                expression_start = current
                while tokens[current] != ';':
                    current += 1
                expression_tokens = tokens[expression_start:current]
                
                if variable in expression_tokens:
                    raise ValueError(f"Invalid assignment: variable '{variable}' cannot appear in its own expression.")
                
                expr = parse_expression(expression_tokens, 0)
                assignments[variable] = expr
                current += 1
            else:
                current += 1

        return all_variables, assignments, show_instructions

    except ValueError as ve:
        raise ve
    except Exception as e:
        raise ValueError(f"Parsing failed: {e}")



def evaluate_expression(node: Node, values: Dict[str, bool]) -> bool:
    try:
        if node.type == 'boolean':
            return node.value == 'True'
        elif node.type == 'variable':
            return values[node.value]
        elif node.type == 'not':
            return not evaluate_expression(node.left, values)
        elif node.type == 'and':
            return evaluate_expression(node.left, values) and evaluate_expression(node.right, values)
        elif node.type == 'or':
            return evaluate_expression(node.left, values) or evaluate_expression(node.right, values)
        else:
            raise ValueError(f"Invalid node type: {node.type}")
    except KeyError as ke:
        raise ValueError(f"Undefined variable: {ke}")
    except Exception as e:
        raise ValueError(f"Evaluation failed: {e}")


def process_chunk(chunk_args):
    try:
        variables, assignments, parsed_instructions, assignments_to_show, start, end = chunk_args
        results = []

        for i in range(start, end):
            values = {var: bool(int(bit)) for var, bit in zip(variables, f'{i:0{len(variables)}b}')}
            row = [str(int(values[var])) for var in variables]

            # Evaluate all assignments to have them available
            for var, expr in assignments.items():
                values[var] = evaluate_expression(expr, values)

            for instruction in parsed_instructions:
                output = row.copy()
                # Only add the final show expression results
                for expr in instruction['identifiers']:
                    result = evaluate_expression(expr, values)
                    output.append('1' if result else '0')

                if instruction['type'] == 'show' or (instruction['type'] == 'show_ones' and output[-1] == '1'):
                    results.append('  ' + ' '.join(output))

        return results
    except Exception as e:
        raise ValueError(f"Chunk processing failed: {e}")


def generate_truth_table(variables: List[str], assignments: Dict[str, Node], show_instructions: List[Dict[str, Union[str, List[str]]]]):
    for instruction in show_instructions:
        # Use only the variables available at this show instruction
        current_vars = instruction['vars']
        current_assignments = instruction['assignments']
        
        # Print header with variables and show expressions
        header = '#   ' + '   '.join(current_vars + instruction['identifiers'])
        print(header)

        # Parse the show expressions
        parsed_identifiers = [
            parse_expression(re.findall(r'\b(?:not|and|or|True|False)\b|\w+|[()]', identifier), 0)
            for identifier in instruction['identifiers']
        ]

        # Generate all possible combinations for current variables
        num_vars = len(current_vars)
        for i in range(2 ** num_vars):
            # Create binary representation for this row
            binary = format(i, f'0{num_vars}b')
            values = {var: bool(int(bit)) for var, bit in zip(current_vars, binary)}
            
            # Evaluate assignments in order
            for var, expr in current_assignments.items():
                values[var] = evaluate_expression(expr, values)
            
            # Evaluate show expressions
            results = []
            for expr in parsed_identifiers:
                result = evaluate_expression(expr, values)
                results.append('1' if result else '0')
            
            # Format and print the row
            var_values = ['1' if values[var] else '0' for var in current_vars]
            if instruction['type'] == 'show' or (instruction['type'] == 'show_ones' and '1' in results):
                row = '    ' + '   '.join(var_values + results)
                print(row)
        
        print()  # Empty line between tables

def process_input(input_text):
    try:
        tokens = tokenize(input_text)
        check_input_syntax(tokens)  # Comprehensive syntax check
        variables, assignments, show_instructions = parse(tokens)
        generate_truth_table(variables, assignments, show_instructions)
    except Exception as e:
        raise ValueError(f"Input processing failed: {e}")


# Read from input.txt and process
if __name__ == '__main__':
    try:
        with open('input.txt', 'r') as file:
            input_text = file.read()

        process_input(input_text)
        print("Process finished --- %s seconds ---" % (time.time() - start_time))
    except Exception as e:
        print(f"Error: {e}")
