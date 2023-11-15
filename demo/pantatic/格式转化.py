v=2

print(v ** (1 / 3) % 1 == 0)

assert v ** (1 / 3) % 1 == 0, f'{v} is not a cubed number'
