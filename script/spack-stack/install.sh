#!/bin/bash

# git pull && time bash install.sh 2>&1 | tee out.install.sh

set -ue

source ./env.sh

# clone spack-stack --------------------------------------------------------------------------------

#cd ${sandbox}
#rm -rf spack-stack || "cannot remove spack-stack"
#git clone ${spack_stack_branch} --recurse-submodules https://github.com/JCSDA/spack-stack
#pushd ./spack-stack/configs/sites/tier1/${site}
#mv mirrors.yaml no.mirrors.yaml
#popd

#pushd ${sandbox}/spack-stack/spack
#git fetch
#git checkout 324bf79 -- var/spack/repos/builtin/packages/py-netcdf4/package.py
#popd

# build env ----------------------------------------------------------------------------------------

cp ${upstream_env}/site/packages.yaml ${sandbox}/spack-stack/configs/sites/tier1/${site}/packages.yaml

cd ${sandbox}/spack-stack
. ./setup.sh

env_to_remove=${sandbox}/spack-stack/envs/${env_name}
echo "env_to_remove=${env_to_remove}"
rm -rf ${env_to_remove} || echo "nothing to remove"
spack stack create env --name ${env_name} --template empty --site ${site} --compiler oneapi \
    ${upstream}

cd ./envs/${env_name}
spack env activate .

spack add \
  py-netcdf4 \
  esmf+python@8.9.1 \
  py-pytest \
  py-xarray \
  prod-util \
  py-pydantic@2.10.1 \
  py-pydantic-settings \
  nccmp
spack concretize --force --fresh
spack clean -a
spack install --verbose --fail-fast
spack module lmod refresh --upstream-modules
spack stack setup-meta-modules
