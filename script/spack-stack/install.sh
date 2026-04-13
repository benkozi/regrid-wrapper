#!/bin/bash

# git pull && time bash install.sh 2>&1 | tee out.install.sh

set -ue

source ./env.sh

# clone spack-stack --------------------------------------------------------------------------------

cd ${sandbox}
rm -rf ${spack_stack_dirname} || "cannot remove spack-stack"
git clone --depth 1 ${spack_stack_branch} --recurse-submodules https://github.com/JCSDA/spack-stack ${spack_stack_dirname}
pushd ./${spack_stack_dirname}/configs/sites/tier1/${site}
mv mirrors.yaml no.mirrors.yaml
popd

# checkout specific hash ---------------------------------------------------------------------------

#pushd ${sandbox}/${spack_stack_dirname}/spack
#git fetch
#git checkout 324bf79 -- var/spack/repos/builtin/packages/py-netcdf4/package.py
#popd

# build env ----------------------------------------------------------------------------------------

cp ${upstream_env}/site/packages.yaml ${sandbox}/${spack_stack_dirname}/configs/sites/tier1/${site}/packages.yaml

cd ${sandbox}/${spack_stack_dirname}
. ./setup.sh

env_to_remove=${sandbox}/${spack_stack_dirname}/envs/${env_name}
echo "env_to_remove=${env_to_remove}"
rm -rf ${env_to_remove} || echo "nothing to remove"
spack stack create env --name ${env_name} --template empty --site ${site} --compiler oneapi \
    ${upstream}

cd ./envs/${env_name}
spack env activate .

spack config add packages:py-netcdf4:require:+mpi
spack config add packages:py-xarray:require:+parallel

spack add \
  py-netcdf4+mpi@1.7.2 \
  esmf+python@8.9.1 \
  py-pytest@8.2.1 \
  py-xarray+parallel@2024.7.0 \
  prod-util \
  py-pydantic@2.10.1 \
  py-pydantic-settings@2.6.1 \
  nccmp
spack concretize --force --fresh
spack clean -a
spack install --verbose --fail-fast
spack module lmod refresh --upstream-modules
spack stack setup-meta-modules
