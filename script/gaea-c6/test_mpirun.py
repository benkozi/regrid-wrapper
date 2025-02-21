from mpi4py import MPI


def test() -> None:
    comm = MPI.COMM_WORLD
    print(comm.Get_rank(), flush=True)


if __name__ == "__main__":
    test()
