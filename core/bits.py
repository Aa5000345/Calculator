"""位运算：补码、位宽、常见运算。"""

def _mask(width):
    return (1 << width) - 1


def to_unsigned(value, width):
    v = int(value) & _mask(width)
    return v


def to_signed(value, width):
    v = int(value) & _mask(width)
    if v & (1 << (width - 1)):
        v -= (1 << width)
    return v


def twos_complement(value, width):
    return to_signed(value, width)


def bit_bin(value, width):
    return format(int(value) & _mask(width), f"0{width}b")


def bit_hex(value, width):
    return format(int(value) & _mask(width), f"0{(width + 3) // 4}X")


def bit_op(a, b, op, width=32):
    a, b = to_unsigned(a, width), to_unsigned(b, width)
    if op == "and":
        r = a & b
    elif op == "or":
        r = a | b
    elif op == "xor":
        r = a ^ b
    elif op == "not":
        r = (~a) & _mask(width)
    elif op == "shl":
        r = (a << b) & _mask(width)
    elif op == "shr":
        r = (a >> b) & _mask(width)
    else:
        raise ValueError(f"未知运算：{op}")
    return r