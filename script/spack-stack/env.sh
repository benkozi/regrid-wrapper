#!/usr/bin/env bash

env_name=mpas-aerosols
spack_stack_dirname=spack-stack-v2

# gaea-c6 ==========================================================================================

#site=gaea-c6
#sandbox=/gpfs/f6/bil-fire8/world-shared/Benjamin.Koziol/mpas-aerosols
##spack_stack_branch="--branch 1.9.2"
#spack_stack_branch=""
##upstream=/autofs/ncrc-svm1_proj/epic/spack-stack/c6/spack-stack-1.9.2/envs/ue-oneapi-2024.2.1/install
#upstream_root=
#upstream_env=/autofs/ncrc-svm1_proj/epic/spack-stack/c6/spack-stack-2.1.0/envs/ue-oneapi-2025.2.1
#upstream="--upstream ${upstream_env}/install"

# ursa =============================================================================================

site=ursa
sandbox=/scratch3/NCEPDEV/stmp/Benjamin.Koziol/sandbox
upstream_env=/contrib/spack-stack/spack-stack-2.1.0/envs/ue-oneapi-2025.3.1
upstream="--upstream ${upstream_env}/install"
spack_stack_branch=""
