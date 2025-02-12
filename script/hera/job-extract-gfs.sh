#!/bin/ksh --login

#SBATCH --time=01:00:00
#_SBATCH --time=18:00:00
#SBATCH --qos=batch
#SBATCH --partition=service
#SBATCH --ntasks=1
#SBATCH --account=epic
#SBATCH --job-name=GFS_extract
#SBATCH --output=/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/data/GFS_NA/GFS_extract.log

  set -xue

# Wall time was 10h; this is insufficient for 15 days.
  # Set dates of interest

  typeset -RZ4 year=2019
  typeset -RZ2 yr=19
  typeset -RZ2 month=08
  typeset -RZ2 day=07
  typeset -RZ2 dayEND=08
  typeset -RZ2 hour=00
  typeset -RZ2 hr=0
  module load hpss
  module load wgrib2

  # Set destination directories (just set first one)
  export DEST_DIR=/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/data/GFS_NA
  cd ${DEST_DIR}

  while [[ ${day} -le ${dayEND} ]] ;
  do
      hsi get /BMC/fdr/Permanent/${year}/${month}/${day}/grib/ftp/7/0/96/0_1038240_0/${year}${month}${day}${hour}00.zip
      unzip ${year}${month}${day}${hour}00.zip;
    day=$((day + 1))
    hr=$((hr + 1))
  done

exit 0
