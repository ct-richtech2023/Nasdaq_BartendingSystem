def foo(name):
    print("starting...", name)
    for i in range(1):
        res = yield 4
        print("22")
        print("res:", res)
    # while True:


if __name__ == "__main__":
    g = foo('wy')
    # print(next(g))
    # print("*"*20)
    # print(next(g))
    # print("*"*20)
    # print(next(g))
