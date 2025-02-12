#!/bin/ksh --login
#SBATCH --time=1:00:00
#_SBATCH --time=5:00:00
#SBATCH --qos=batch
#SBATCH --partition=service
#SBATCH --ntasks=1
#SBATCH --account=epic
#SBATCH --job-name=GFS_extract
#SBATCH --output=/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/data/GFS_NA/GFS_extract.log

  # origin = /scratch1/BMC/acomp/Johana/to_share1/for_Haiqin/2020_NA_retro/extract_GFS.sh
  set -xue

# Wall time was 10h; this is insufficient for 15 days.
  # Set dates of interest

  typeset -RZ4 year=2019
  typeset -RZ2 yr=19
  typeset -RZ2 month=07
  typeset -RZ2 day=22
  typeset -RZ2 dayEND=23
  typeset -RZ2 hour=0
  typeset -RZ3 julian=245
  typeset -RZ2 hr=0
  module load hpss
  module load wgrib2

  # Set destination directories (just set first one)
  export DEST_DIR=/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/data/GFS_NA
  cd ${DEST_DIR}

  while [[ ${day} -le ${dayEND} ]] ;
  do
      #hsi get /NCEPPROD/hpssprod/runhistory/rh2020/${year}${month}/${year}${month}${day}/com_gfs_prod_gfs.${year}${month}${day}_00.gfs_pgrb2.tar
      while [[ ${hr} -le 60 ]] ;
       do
        if [ $hr -lt 10 ] ; then
          hr=0${hr}
         echo $hr
        fi
         htar -xvf /NCEPPROD/hpssprod/runhistory/rh2020/202009/202009${day}/com_gfs_prod_gfs.202009${day}_00.gfs_pgrb2.tar ./gfs.202009${day}/00/gfs.t00z.pgrb2.0p25.f0${hr}

         mv ${DEST_DIR}/gfs.${year}${month}${day}/00/gfs.t00z.pgrb2.0p25.f0${hr} ${DEST_DIR}/20${julian}000000${hr}
         hr=$((hr + 1))
       done
      day=$((day + 1))
      julian=$((julian + 1))
      hr=0
      rm -fr ${DEST_DIR}/gfs.${year}${month}${day}
      rm -fr ${DEST_DIR}/com_gfs_prod_gfs.${year}${month}${day}_00.gfs_pgrb2.tar
  done

exit 0