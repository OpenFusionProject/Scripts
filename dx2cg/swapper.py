#!/usr/bin/env python
# coding: utf-8
# parser for replacing d3d9 subprograms in shaderlab files with HLSL/CG
# ycc 08/08/2022

import re
from disassembler import disassemble

tabs = 3
def indent(block):
    lines = block.split('\n')
    for i in range(0, len(lines)-1):
        lines[i] = tabs * "\t" + lines[i]
    return "\n".join(lines)

def find_closing_bracket(block, i):
    count = 0;
    while i < len(block):
        if block[i] == '{':
            count = count + 1
        if block[i] == '}':
            count = count - 1
            if count == 0:
                return i
        i = i + 1
    raise ValueError(f"Block at {i} has no closing bracket")

def process_program(prog):
    subprog_index = prog.find("SubProgram \"d3d9")
    if subprog_index == -1:
        raise ValueError(f"Program has no d3d9 subprogram")
    subprog_end_index = find_closing_bracket(prog, subprog_index)
    subprog = prog[subprog_index:subprog_end_index+1]
    processed = disassemble(subprog) + "\n"
    return indent(processed)

def process_shader(shader):
    buf = shader
    processed = ''
    program_index = buf.find('Program')
    while program_index > -1:
        processed = processed + buf[:program_index]
        buf = buf[program_index:]
        line = re.search("#LINE [0-9]+\n", buf)
        if not line:
            raise ValueError(f"Program at {program_index} has no #LINE marker")
        end_index = line.end() + 1
        program_section = buf[program_index:end_index+1]
        processed = processed + process_program(program_section)
        buf = buf[end_index+1:]
        
        program_index = buf.find('Program')
    processed = processed + buf
    return processed

def process(fn_in, fn_out):
    with open(fn_in, "r") as fi:
        buf = fi.read()
        processed = process_shader(buf)
    if buf != processed:
        with open(fn_out, "w") as fo:
            fo.write(processed)
        return True
    return False
