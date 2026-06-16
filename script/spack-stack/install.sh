#!/bin/bash

# git pull && time bash install.sh 2>&1 | tee out.install.$(date +%Y%m%d-%H%M%S)

set -ue

source ./env.sh

_cwd=$(readlink -f .)

# clone spack-stack --------------------------------------------------------------------------------

cd ${sandbox}
#rm -rf ${spack_stack_dirname} || "cannot remove spack-stack"
git clone ${spack_stack_branch} https://github.com/JCSDA/spack-stack ${spack_stack_dirname}
pushd ${spack_stack_dirname}
git checkout 37c009d # version 2.1.1
git submodule update --init --recursive
popd
pushd ./${spack_stack_dirname}/configs/sites/tier1/${site}
mv mirrors.yaml no.mirrors.yaml
popd

# patch esmf ---------------------------------------------------------------------------------------

git apply ${_cwd}/esmf-version.patch

# build env ----------------------------------------------------------------------------------------

cp ${upstream_env}/site/packages.yaml ${sandbox}/${spack_stack_dirname}/configs/sites/tier1/${site}/packages.yaml

cd ${sandbox}/${spack_stack_dirname}
. ./setup.sh

#env_to_remove=${sandbox}/${spack_stack_dirname}/envs/${env_name}
#echo "env_to_remove=${env_to_remove}"
#rm -rf ${env_to_remove} || echo "nothing to remove"
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
spack module lmod refresh --upstream-modules -y
spack stack setup-meta-modules
