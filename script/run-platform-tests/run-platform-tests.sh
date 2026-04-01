#!/bin/bash

# git pull && time bash run-platform-tests.sh 2>&1 | tee out.run-platform-tests.sh

set -eu
source ./env-run-platform-tests.sh
set -x

if [[ ${run_unit_tests} == "TRUE" ]]; then
  srun --export=ALL --account ${account} --ntasks 1 --time 00:01:00 ${cluster} ${partition} pytest -vs ${rw_dir}/src/test
  srun --export=ALL --account ${account} --ntasks 8 --time 00:01:00 ${cluster} ${partition} pytest -vs -m "mpi and not integration" ${rw_dir}/src/test
fi

if [[ ${run_chem_regrid} == "TRUE" ]]; then
  if [[ ${cr_clean_output_dir} == "TRUE" ]]; then
    rm -rf ${cr_output_dir:?}/* || "nothing to remove in cr_output_dir"
  fi
  srun --export=ALL --account ${account} --ntasks ${cr_ntasks} --time ${cr_wtime} ${cluster} ${partition} python ${rw_dir}/src/regrid_wrapper/app/chem_regrid.py \
    ${cr_dataset_name} \
    ${cr_workdir} \
    ${cr_input_dir} \
    ${cr_output_dir} \
    ${cr_weight_dir} \
    ${cr_cycle}
    ${cr_scrip_path} \
    ${cr_dst_path}
fi
