# Third-party source and licenses

The enhancer RTL, host and board scripts in vision_enhancer are MIT licensed.
The official PYNQ v2.4 source used for the build was supplied at
C:\fpga\vision\PYNQ and staged for the current build at the sibling
work/p2 directory. The earlier work/pynq_v2_4 directory holds diagnostic
evidence from an interrupted build.
Its original LICENSE and THIRD_PARTY_LIC files are preserved there.
The source tree contains Xilinx/AMD, Digilent and other components
under their original terms; this project does not relicense them.

The pinned source revision recorded by the earlier project is
d9c752164644ebdbf7f96e4cd7d96661d1276a34. This Windows copy is
an extracted archive without .git, so the hash is provenance from the
previous manifest, not a new git rev-parse result. Keep download
manifests and original archives when publishing the submission.
The official base.bit/base.hwh are reference artifacts and do not
contain the vision enhancer.

Upgrade v2 uses the separate sibling work/p3 directory. Its original licenses are preserved. The release includes pynq_v24_required_sources.zip with the required vendor source paths and a file hash manifest. The recorded source revision remains provenance, not a freshly verified Git revision.
