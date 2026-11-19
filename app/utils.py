def format_inr(amount, include_symbol=True, decimals=False) -> str:
    """
    Format a number in Indian Rupee format (e.g. ₹100, ₹1,000, ₹10,000, ₹1,00,000).
    """
    if amount is None:
        return '₹0' if include_symbol else '0'
    try:
        val = float(amount)
    except (ValueError, TypeError):
        return str(amount)

    is_neg = val < 0
    abs_val = abs(val)

    if decimals and (abs_val != int(abs_val)):
        dec_part = f"{abs_val:.2f}".split('.')[1]
        int_str = str(int(abs_val))
    else:
        dec_part = None
        int_str = str(int(round(abs_val)))

    if len(int_str) <= 3:
        formatted = int_str
    else:
        last3 = int_str[-3:]
        rest = int_str[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted = ','.join(groups) + ',' + last3

    if dec_part:
        formatted = f"{formatted}.{dec_part}"

    prefix = '₹' if include_symbol else ''
    if is_neg:
        return f"-{prefix}{formatted}"
    return f"{prefix}{formatted}"
