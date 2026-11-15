"""
agent.py
Plantilla oficial de l'agent de control per al repte de la bateria de UPC Sostenible.
Datathon 2026.
"""

# import joblib  # Descomenteu si utilitzeu models serialitzats (.pkl)

class BatteryAgent:
    def __init__(self):
        """Inicialització de l'agent.
        S'executa una sola vegada a l'inici del període d'avaluació.
        Permet carregar models predictius o definir llindars d'operació.
        """
        # Paràmetres d'operació de la política de referència
        self.llindar_preu_carrega = 0.08      # €/kWh
        self.llindar_preu_descarrega = 0.16   # €/kWh
        self.potencia_nominal_kw = 500.0      # Potència màxima de l'inversor (kW)

        # Memòria històrica d'hores passades (permet consultar el passat dins de la simulació):
        # self.historial = []
        self.capacitat = 2000.0
        self.rendiment_eta = 0.9487
        self.rendiment_cicle = self.rendiment_eta ** 2
        self.soc_minim = 0.10
        self.soc_maxim = 0.98
        self.pes_co2 = 0.60
        self.pes_preu = 0.40
        self.perfils_consum = {}

    def act(self, obs: dict) -> float:
        """Determina la consigna de potència activa de la bateria per a l'hora actual.

        Paràmetres:
        -----------
        obs : dict amb les variables d'estat disponibles a l'hora actual:
            - "timestamp": pd.Timestamp amb la data i hora d'avaluació.
            - "hour": int de 0 a 23 (hora del dia).
            - "day_of_week": int de 0 (dilluns) a 6 (diumenge).
            - "soc_kwh": float amb l'energia emmagatzemada actual (0.0 a 2.000.0 kWh).
            - "soc_pct": float amb l'estat de càrrega relatiu [0.0, 1.0].
            - "preu_actual": float amb el preu del PVPC d'aquesta hora (€/kWh).
            - "co2_actual": float amb la intensitat de CO2 peninsular (kg CO2/kWh).
            - "preus_properes_24h": llista de preus horaris de les properes 24 hores (€/kWh).
            - "co2_properes_24h": llista de factors d'emissió de CO2 de les properes 24 hores (kg/kWh).
            - "noves_dades_5min": dades mesurades pels sensors en la darrera hora transcorreguda.

        Retorna:
        --------
        float : Consigna de potència activa en kW:
            > 0  -> Càrrega d'energia des de la xarxa interna (fins a +500.0 kW).
            < 0  -> Descàrrega d'energia cap al campus (fins a -500.0 kW).
            = 0  -> Bateria en mode d'espera (0.0 kW).
        """
        timestamp = obs["timestamp"]
        mes = timestamp.month
        hora = obs["hour"]
        dia_setmana = obs["day_of_week"]
        es_finde = dia_setmana >= 5

        soc = obs["soc_pct"]
        soc_kwh = obs["soc_kwh"]

        preus_24h = list(obs["preus_properes_24h"])
        co2_24h = list(obs["co2_properes_24h"])

        dades_5min = obs["noves_dades_5min"]
        ultim_consum = dades_5min["ultim_consum_kw"]
        ultima_solar = dades_5min["ultima_solar_kw"]

        # Guardem observació al perfil (mes, es_finde, hora)
        clau_perfil = (mes, es_finde, hora)
        if clau_perfil not in self.perfils_consum:
            self.perfils_consum[clau_perfil] = []
        self.perfils_consum[clau_perfil].append(ultim_consum)

        # Estimació de consum basada en l'historial del mateix mes i tipus de dia
        historial_grup = self.perfils_consum[clau_perfil]
        if len(historial_grup) >= 3:
            consum_estimat = sum(historial_grup) / len(historial_grup)
        else:
            consum_estimat = ultim_consum

        excedent_solar = max(0.0, ultima_solar - ultim_consum)
        demanda_neta_estimada = max(0.0, consum_estimat - ultima_solar)

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

        puntuacio_actual = puntuacions
        puntuacions_ordenades = sorted(puntuacions)

        llindar_carrega = puntuacions_ordenades[int((n - 1) * 0.25)]
        llindar_descarrega = puntuacions_ordenades[int((n - 1) * 0.65)]

        marge_preu = (p_max * self.rendiment_cicle) > p_min
        marge_co2 = (c_max * self.rendiment_cicle) > c_min
        cicle_rendible = marge_preu or marge_co2

        consigna = 0.0

        if excedent_solar > 0 and soc < self.soc_maxim:
            consigna = min(self.potencia_nominal_kw, excedent_solar)

        elif puntuacio_actual <= llindar_carrega and cicle_rendible:
            # Si és cap de setmana o mes d'estiu (juliol/agost), carreguem menys de la xarxa
            if es_finde or mes in (7, 8):
                limit_soc = 0.65
            elif 1 <= hora <= 8:
                limit_soc = 0.85
            else:
                limit_soc = self.soc_maxim

            if soc < limit_soc:
                consigna = self.potencia_nominal_kw

        elif puntuacio_actual >= llindar_descarrega and soc > self.soc_minim and cicle_rendible:
            # Ajustem la descàrrega a la demanda estimada del perfil (mes, finde, hora)
            potencia_objectiu = max(demanda_neta_estimada, 150.0) if es_finde else self.potencia_nominal_kw
            consigna = -min(self.potencia_nominal_kw, potencia_objectiu)

        max_carrega = min(
            self.potencia_nominal_kw,
            max(0.0, (self.capacitat * self.soc_maxim - soc_kwh) / self.rendiment_eta)
        )
        max_descarrega = min(
            self.potencia_nominal_kw,
            max(0.0, (soc_kwh - self.capacitat * self.soc_minim) * self.rendiment_eta)
        )

        consigna = max(-max_descarrega, min(max_carrega, consigna))
        return float(consigna)
