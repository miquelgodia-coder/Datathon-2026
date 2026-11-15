"""
agent.py
Plantilla oficial de l'agent de control per al repte de la bateria de UPC Sostenible.
Datathon 2026 - Versió corregida i agressiva.
"""

class BatteryAgent:

    def __init__(self):
        self.potencia_nominal_kw = 500.0
        self.capacitat = 2000.0
        self.rendiment_eta = 0.9487
        self.rendiment_cicle = self.rendiment_eta ** 2  # ~0.90

        self.soc_minim = 0.10
        self.soc_maxim = 0.98

        
        self.pes_co2 = 0.70
        self.pes_preu = 0.30

    def act(self, obs):
        hora = obs["hour"]
        soc = obs["soc_pct"]
        soc_kwh = obs["soc_kwh"]

        preus_24h = list(obs["preus_properes_24h"])
        co2_24h = list(obs["co2_properes_24h"])

        dades_5min = obs["noves_dades_5min"]
        ultim_consum = dades_5min["ultim_consum_kw"]
        ultima_solar = dades_5min["ultima_solar_kw"]

        excedent_solar = max(0.0, ultima_solar - ultim_consum)
        demanda_neta = max(0.0, ultim_consum - ultima_solar)

        n = min(len(preus_24h), len(co2_24h))
        if n == 0:
            return 0.0

        
        p_min, p_max = min(preus_24h[:n]), max(preus_24h[:n])
        c_min, c_max = min(co2_24h[:n]), max(co2_24h[:n])

        puntuacions = []
        for i in range(n):
            p_norm = (preus_24h[i] - p_min) / (p_max - p_min) if p_max > p_min else 0.5
            c_norm = (co2_24h[i] - c_min) / (c_max - c_min) if c_max > c_min else 0.5
            puntuacions.append(self.pes_co2 * c_norm + self.pes_preu * p_norm)

        
        puntuacio_actual = puntuacions[0]
        puntuacions_ordenades = sorted(puntuacions)

        # Mirem les 6 hores més barates (25%) i les 8 hores més cares (top 33%)
        llindar_carrega = puntuacions_ordenades[int((n - 1) * 0.25)]
        llindar_descarrega = puntuacions_ordenades[int((n - 1) * 0.65)]

       
        marge_preu = (p_max * self.rendiment_cicle) > p_min
        marge_co2 = (c_max * self.rendiment_cicle) > c_min
        cicle_rendible = marge_preu or marge_co2

        consigna = 0.0

        # Excedent solar: guardar sempre
        if excedent_solar > 0 and soc < self.soc_maxim:
            consigna = min(self.potencia_nominal_kw, excedent_solar)

        # Carregar en hores preu baix
        elif puntuacio_actual <= llindar_carrega and cicle_rendible:
            # De matinada deixem un 15% lliure pel sol del migdia
            limit_soc = 0.85 if (1 <= hora <= 8) else self.soc_maxim
            if soc < limit_soc:
                consigna = self.potencia_nominal_kw

        # Descarregar en hores preu alt
        elif puntuacio_actual >= llindar_descarrega and soc > self.soc_minim and cicle_rendible:
            consigna = -self.potencia_nominal_kw

        # Límits 
        max_carrega = min(self.potencia_nominal_kw,max(0.0, (self.capacitat * self.soc_maxim - soc_kwh) / self.rendiment_eta))
        max_descarrega = min(self.potencia_nominal_kw,max(0.0, (soc_kwh - self.capacitat * self.soc_minim) * self.rendiment_eta))

        consigna = max(-max_descarrega, min(max_carrega, consigna))
        return float(consigna)
