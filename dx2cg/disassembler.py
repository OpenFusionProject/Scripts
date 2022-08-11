#!/usr/bin/env python
# coding: utf-8
# d3d9 to cg crude dissassembler
# ycc 08/08/2022

import re
import sys

legacy = False # True for 2.6

reserved = {
    "_Time",
    "_SinTime",
    "_CosTime",
    
    "_ProjectionParams",
    
    "_PPLAmbient",
    
    "_ObjectSpaceCameraPos",
    "_ObjectSpaceLightPos0",
    "_ModelLightColor0",
    "_SpecularLightColor0",
    
    "_Light2World0", "_World2Light0", "_Object2World", "_World2Object", "_Object2Light0",
    
    "_LightDirectionBias",
    "_LightPositionRange",
}

decls = {
    "dcl_position": "float4 {0} = vdat.vertex;",
    "dcl_normal": "float4 {0} = float4(vdat.normal.x, vdat.normal.y, vdat.normal.z, 0);",
    "dcl_texcoord0": "float4 {0} = vdat.texcoord;",
    "dcl_texcoord1": "float4 {0} = vdat.texcoord1;",
    "dcl_color": "float4 {0} = vdat.color;",
    "dcl_2d": "; // no operation",
    "dcl": "float4 {0[0]}{0[1]} = pdat.{0[0]}{0[1]};",
    "def": "const float4 {0} = float4({1}, {2}, {3}, {4});",
}

ops = {
    "mov": "{0} = {1};",
    "add": "{0} = {1} + {2};",
    "mul": "{0} = {1} * {2};",
    "mad": "{0} = {1} * {2} + {3};",
    "dp4": "{0} = dot((float4){1}, (float4){2});",
    "dp3": "{0} = dot((float3){1}, (float3){2});",
    "min": "{0} = min({1}, {2});",
    "max": "{0} = max({1}, {2});",
    "rsq": "{0} = rsqrt({1});",
    "frc": "{0} = float4({1}.x - (float)floor({1}.x), {1}.y - (float)floor({1}.y), {1}.z - (float)floor({1}.z), {1}.w - (float)floor({1}.w));",
    "slt": "{0} = float4(({1}.x < {2}.x) ? 1.0f : 0.0f, ({1}.y < {2}.y) ? 1.0f : 0.0f, ({1}.z < {2}.z) ? 1.0f : 0.0f, ({1}.w < {2}.w) ? 1.0f : 0.0f);",
    "sge": "{0} = float4(({1}.x >= {2}.x) ? 1.0f : 0.0f, ({1}.y >= {2}.y) ? 1.0f : 0.0f, ({1}.z >= {2}.z) ? 1.0f : 0.0f, ({1}.w >= {2}.w) ? 1.0f : 0.0f);",
    "rcp": "{0} = ({1} == 0.0f) ? FLT_MAX : (({1} == 1.0f) ? {1} : (1 / {1}));",
    "texld": "{0} = tex2D({2}, (float2){1});",
}

struct_a2v = """struct a2v {
\tfloat4 vertex : POSITION;
\tfloat3 normal : NORMAL;
\tfloat4 texcoord : TEXCOORD0;
\tfloat4 texcoord1 : TEXCOORD1;
\tfloat4 tangent : TANGENT;
\tfloat4 color : COLOR;
};
"""

v2f_postype = "POSITION" if legacy else "SV_POSITION"
struct_v2f = f"""struct v2f {{
\tfloat4 pos : {v2f_postype};
\tfloat4 t0 : TEXCOORD0;
\tfloat4 t1 : TEXCOORD1;
\tfloat4 t2 : TEXCOORD2;
\tfloat4 t3 : TEXCOORD3;
\tfloat fog : FOG;
\tfloat4 d0 : COLOR0;
\tfloat4 d1 : COLOR1;
}};
"""

struct_f2a = """struct f2a {
\tfloat4 c0;
};
"""

cg_header = """CGPROGRAM
#include "UnityCG.cginc"
#pragma exclude_renderers xbox360 ps3 gles
"""

cg_footer = """ENDCG"""

vertex_func = """v2f vert(a2v vdat) {{
\tfloat4 r0, r1, r2, r3, r4;
\tfloat4 tmp;
\tv2f o;

{0}

\treturn o;
}}
"""

fragment_func = """f2a frag(v2f pdat) {{
\tfloat4 r0, r1, r2, r3, r4;
\tfloat4 tmp;
\tf2a o;

{0}

\treturn o;
}}
"""

def process_header(prog):
    keywords = []
    loctab = {}
    locdecl = []
    binds = []
    i = 0
    lighting = False
    textures = 0
    while i < len(prog):
        line = prog[i]
        if line.startswith("Keywords"):
            keywords = re.findall("\"[\w\d]+\"", line)
            del prog[i]
            i = i - 1
        elif line.startswith("Bind"):
            binds.append(line)
            del prog[i]
            i = i - 1
        elif line.startswith("Local") or line.startswith("Matrix"):
            dec = line.split(' ')
            key = int(dec[1][:-1])
            if dec[2][0] == '[':
                # singleton
                val = dec[2][1:-1]
                if val[0] == '_' and val not in reserved:
                    loctype = "float4" if dec[0] == "Local" else "float4x4"
                    locdecl.append(f"{loctype} {val};")
            elif dec[2][0] == '(':
                #components
                vals = dec[2][1:-1].split(',')
                for j, v in enumerate(vals):
                    if v[0] == '[':
                        vals[j] = v[1:-1]
                        if vals[j][0] == '_' and vals[j] not in reserved:
                            locdecl.append(f"float {vals[j]};")
                val = f"float4({vals[0]},{vals[1]},{vals[2]},{vals[3]})"
            
            lightval = re.match("glstate_light(\d)_([a-zA-Z]+)", val)
            if lightval:
                val = f"glstate.light[{lightval[1]}].{lightval[2]}"
                lighting = True
            elif val == "_ObjectSpaceCameraPos" and not legacy:
                val = "mul(_World2Object, float4(_WorldSpaceCameraPos.x, _WorldSpaceCameraPos.y, _WorldSpaceCameraPos.z, 0))"
            elif val == "_ObjectSpaceLightPos0" and not legacy:
                val = "mul(_World2Object, _WorldSpaceLightPos0)"
                lighting = True
            elif val == "glstate_lightmodel_ambient":
                val = "glstate.lightmodel.ambient"
                lighting = True
            elif val.startswith("glstate_matrix_texture"):
                val = f"glstate.matrix.texture[{val[-1]}]" if legacy else f"UNITY_MATRIX_TEXTURE{val[-1]}"
            elif val == "glstate_matrix_mvp":
                val = "glstate.matrix.mvp" if legacy else "UNITY_MATRIX_MVP"
            elif val == "glstate_matrix_modelview0":
                val = "glstate.matrix.modelview[0]" if legacy else "UNITY_MATRIX_MV"
            elif val == "glstate_matrix_transpose_modelview0":
                val = "glstate.matrix.transpose.modelview[0]" if legacy else "UNITY_MATRIX_T_MV"
            elif val == "glstate_matrix_invtrans_modelview0":
                val = "glstate.matrix.invtrans.modelview[0]" if legacy else "UNITY_MATRIX_IT_MV"
            elif val.startswith("glstate"):
                raise ValueError(f"Unrecognized glstate: {val}")
                
            if dec[0] == "Local":
                loctab[f"c{key}"] = val
            elif dec[0] == "Matrix":
                for offset in range(0,4):
                    loctab[f"c{key + offset}"] = f"{val}[{offset}]"
            
            del prog[i]
            i = i - 1
        elif line.startswith("SetTexture"):
            dec = line.split(' ')
            if dec[2] !=  "{2D}":
                raise ValueError(f"Unknown texture type {dec[2]}")
            key = f"s{textures}"
            val = dec[1][1:-1]
            loctab[key] = val
            locdecl.append(f"sampler2D {val};")
            textures = textures + 1

            del prog[i]
            i = i - 1
        i = i + 1

    # print(loctab)
    
    return (keywords, loctab, locdecl, binds, lighting)

def resolve_args(args, loctab, consts):
    for a in range(0, len(args)):
        arg = args[a]
        
        neg = ""
        if arg[0] == '-':
            arg = arg[1:]
            neg = "-"
        
        # save swizzler!
        dot = arg.find(".")
        if dot > -1:
            swiz = arg[dot:]
            arg = arg[:dot]
        else:
            swiz = ""
        
        if arg[0] == 'r':
            pass
        elif arg[0] == 'v':
            pass
        elif arg[0] == 't':
            pass
        elif arg[0] == 'c':
            if arg not in consts:
                arg = loctab[arg]
        elif arg[0] == 's':
            arg = loctab[arg]
        elif arg[0] == 'o':
            arg = f"o.{arg[1:].lower()}"
        elif re.match("[+-]?([0-9]*[.])?[0-9]+", arg):
            pass
        else:
            raise ValueError(f"Unknown arg {arg}")
        
        args[a] = neg + arg + swiz

def decode(code, args):
    if code in decls:
        return [decls[code].format(*args)]
    elif code in ops:
        target = args[0]
        if target == "o.fog":
            return [ops[code].format(*args)]
        
        dot = re.search("\.[xyzw]+", target)
        if dot:
            swiz = target[dot.start()+1:]
            target = target[:dot.start()]
        else:
            swiz = "xyzw"
        
        lines = [ops[code].format("tmp", *args[1:])]
        for c in swiz:
            lines.append(f"{target}.{c} = tmp.{c};")
        return lines
    else:
        raise ValueError(f"Unknown opcode {code}")

def process_asm(asm, loctab):
    shadertype = ""
    if asm[0] == "\"vs_1_1":
        shadertype = "vertex"
    elif asm[0] == "\"ps_2_0":
        shadertype = "fragment"
    else:
        raise ValueError(f"Unsupported shader type: {asm[0][1:]}")
    
    consts = set()
    translated = []
    i = 1
    while i < len(asm):
        instruction = asm[i]
        if instruction == "\"":
            break
        
        space = instruction.find(" ")
        if space == -1:
            code = instruction
            args = []
        else:
            code = instruction[:space]
            args = instruction[space+1:].split(", ")

        if code == "def":
            consts.add(args[0])

        pp = code.find("_pp")
        if pp > -1:
            code = code[:pp]
            
        resolve_args(args, loctab, consts)
        disasm = decode(code, args)
        # print(f"{instruction} \t==>\t{disasm}")
        disasm.insert(0, f"// {instruction}")
        translated.extend(disasm)
        i = i + 1
    
    return (shadertype, translated)

def disassemble(blocks):
    shaders = {}
    keywords = set()
    locdecl = set()
    binds = set()
    lighting = False
    for block in blocks:
        asm = block.split('\n')[1:-1]

        (kw, ltab, ldecl, bds, light) = process_header(asm)
        keywords.update(kw)
        locdecl.update(ldecl)
        binds.update(bds)
        lighting |= light

        (shadertype, disasm) = process_asm(asm, ltab)
        shaders[shadertype] = disasm

    text = ""
    if len(binds) > 0:
        text += "BindChannels {\n"
        for b in binds:
            text += f"\t{b}\n"
        text += "}\n"
    
    if lighting:
        text += "Lighting On\n"

    text += cg_header
    if len(keywords) > 0:
        text += "#pragma multi_compile " + " ".join(keywords)
    if "vertex" in shaders:
        text += "#pragma vertex vert\n"
    if "fragment" in shaders:
        text += "#pragma fragment frag\n"
    text += "\n"
    if "vertex" in shaders:
        text += struct_a2v + "\n"
    text += struct_v2f + "\n"
    if "fragment" in shaders:
        text += struct_f2a + "\n"
    text += "\n".join(locdecl) + "\n"
    if "vertex" in shaders:
        text += "\n" + vertex_func.format("\t" + "\n\t".join(shaders["vertex"]))
    if "fragment" in shaders:
        text += "\n" + fragment_func.format("\t" + "\n\t".join(shaders["fragment"]))
    text += cg_footer
    return text

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: disassembler.py <filename>")
    else:
        with open(sys.argv[1], "r") as fi:
            buf = fi.read()
        disasm = disassemble(buf.split('~'))
        print(disasm)
