
def dia_de_la_setmana (d: int, m: int, a: int) -> str:
    m -= 2
    mm = m
    aa = a
    if m <= 0: 
        mm = m + 12
        aa = a - 1
    c = aa // 100
    y = aa - c * 100
    f = int(2.6 * mm - 0.2) + d + y + y//4 + c//4 - 2 * c
    if f % 7 == 0:
        return "diumenge"
    if f % 7 == 1:
        return "dilluns"
    if f % 7 == 2:
        return "dimarts"
    if f % 7 == 3:
        return "dimecres"
    if f % 7 == 4:
        return "dijous"
    if f % 7 == 5:
        return "divendres"
    if f % 7 == 6:
        return "dissabte"

    def es_setmana (d: int, m: int, a: int) -> str:
        """
        Retorna True si és dia de la setmana, utilitzant la congruència de Zeller.
        """
        m -= 2
        mm = m
        aa = a
        if m <= 0: 
            mm = m + 12
            aa = a - 1
        c = aa // 100
        y = aa - c * 100
        f = int(2.6 * mm - 0.2) + d + y + y//4 + c//4 - 2 * c
        if f % 7 == 0 or f % 7 == 6:
            return False
        else:
            return True