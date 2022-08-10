# dx2cg
Tools for converting d3d9 shader assembly to HLSL/Cg.
- `disassembler.py`: Takes in d3d9 assembly and gives back the HLSL equivalent.
- `swapper.py`: Searches a shader file for d3d9 assembly and calls the disassembler to replace it with HLSL.
- `main.py`: Executes the swapper on every file in a path, writing the changes to new files.

## Known issues
- Only vertex shaders with profile `vs_1_1` are supported
- No fragment shaders are supported yet
- Only a limited set of instructions (those used by FF and Unity 2.6) are supported
