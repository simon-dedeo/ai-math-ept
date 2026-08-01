import sys, glob, os
sys.path.insert(0,"code")
import numpy as np
from proofnet import load_edgelist
def hill(d,xm):
    x=np.asarray([v for v in d if v>=xm],float)
    return 1+len(x)/np.sum(np.log(x/(xm-0.5))) if len(x)>=8 else float("nan")
PUB={"wiles_flt":(142,3.39),"apollonius":(446,2.28),"herstein":(280,2.36),
     "orlik_strauch":(61,2.14),"spinoza_ethics":(None,None)}
print("network            N  pubN |  alpha at x_min 2 / 3 / 5 / 10 | published alpha")
for p in sorted(glob.glob("networks/hand_human/*.edges")):
    s=os.path.basename(p)[:-6]
    G=load_edgelist(p,delimiter="\t")
    G.remove_nodes_from([n for n,d in G.degree() if d==0])
    od=np.array([d for _,d in G.out_degree()])
    a=[hill(od,x) for x in (2,3,5,10)]
    pn,pa=PUB.get(s,(None,None))
    cells=" ".join((f"{x:5.2f}" if x==x else "  -- ") for x in a)
    print(f"{s:16s} {G.number_of_nodes():4d} {str(pn):>5s} | {cells} | {pa}")
