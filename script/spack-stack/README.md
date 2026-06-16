1. Update `env.sh` to use the correct platform, environment, and spack-stack directory name. Typically, only the spack-stack directory will need to be incremented.
2. On the target platform, `cd scrip/spack-stack`.
3. If not using `git` or other means to update remote script, modify `env.sh` and `install.sh` as desired on the platform.
4. Run `bash install.sh 2>&1 | tee out.install.$(date +%Y%m%d-%H%M%S)`.
5. Link the new spack-stack environment to whatever is required by dependent modulefiles (i.e., `ln -s <new-spack-stack-dir> <module-spack-stack-dire>`).