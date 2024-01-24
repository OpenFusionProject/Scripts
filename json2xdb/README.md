# json2xdb
This script populates a functional, near-complete FusionFall XDB tabledata server.
You need an existing MySQL server (an old version; 5.5.42 seems to work with the FusionFall client). This can be set up pretty easily using Docker.
You also need a copy of xdt.json from the [OpenFusion tabledata repository](https://github.com/OpenFusionProject/tabledata).

It is interesting to note that the JSON tabledata file is really just a Unity ScriptableObject containing all the XDT/XDB state packaged into a FusionFall client build. The devs likely kept a central tabledata server around (XDB) and, whenever it was time for a client build, they fetched it into local binary files (XDT) before finally packing them into the XdtTableScript asset.

I would like to thank my girlfriend for showing me the wonders of `tqdm`. It really helped being able to see that things were happening. 

