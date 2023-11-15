class A:
    def hahah(self):
        print('23')


class B:
    def hahah(self):
        print('123')


def create_obj():
    return A()


def yes(obj=create_obj()):
    obj.hahah()


if __name__ == '__main__':
    yes()
    yes(B())
