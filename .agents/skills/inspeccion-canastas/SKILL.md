---
name: inspeccion-canastas
description: >-
  Protocolo de inspección visual detallada y conteo dinámico de cualquier número N de canastillas plásticas apiladas.
  Distingue con precisión entre canastas grandes y pequeñas basándose en altura relativa,
  rebordes de encaje, agarraderas, nervaduras verticales y factor de anidamiento.
---

# Protocolo de Inspección Visual Dinámica de Canastas Plásticas (RETORNA)

Este documento define la metodología y reglas de visión por computadora para que el agente RETORNA identifique, clasifique y cuente **cualquier número arbitrario $N$ de canastas** (en pilas individuales o múltiples columnas) a partir de fotografías tomadas por conductores o despachadores.

> [!IMPORTANT]
> **El número de canastas es completamente dinámico ($N$ arbitrario)**.
> Una foto puede contener desde 1 sola canasta hasta pilas de 8, 12, 16 o más niveles, distribuidas en 1 o varias columnas, en cualquier orden o combinación (todas grandes, todas pequeñas, o mixtas).
> El ejemplo anterior de 6 niveles sirvió únicamente para calibrar las proporciones visuales y no representa un límite fijo.

---

## 1. Tipología y Proporciones de Canastas

| Tipo de Canasta | Altura Visible Anidada | Características Visuales Clave | Factor de Escala |
| :--- | :--- | :--- | :--- |
| **Canasta Pequeña** (Bandeja) | Baja (~12 - 16 cm) | • Perfil horizontal angosto y alargado.<br>• Agarradera rectangular centrada de poca altura.<br>• Paredes laterales compactas sin doble fila de nervaduras. | `1x` (Bandeja estándar) |
| **Canasta Grande** (Cajón) | Alta (~25 - 32 cm) | • Altura vertical notablemente mayor (**aprox. el DOBLE / 2x** de una pequeña).<br>• Paneles laterales profundos con nervaduras verticales de refuerzo.<br>• Espacio amplio para grabado/estampado (marcas "BP", "RP", etc.).<br>• Agarraderas ergonómicas más profundas. | `2x` (Cajón alto) |

---

## 2. Metodología de Segmentación Dinámica Nivel por Nivel

Para contar una pila de cualquier altura $N$:

1. **Detección de Columnas / Pilas**:
   - Identificar si la imagen contiene una sola pila vertical o varias columnas adyacentes (ej: 2 pilas de 6 canastas = 12 canastas).
   - Analizar cada columna de forma independiente.

2. **Escaneo Top-Down (De Arriba hacia Abajo)**:
   - Localizar el borde superior de la primera canasta.
   - Avanzar verticalmente hacia abajo buscando cada **línea divisoria horizontal** (reborde de encaje / labio perimetral) y cada **orificio de agarradera**.

3. **Determinación del Tipo por Intervalo de Altura**:
   - Para cada canasta $i$, medir el intervalo vertical visible hasta el siguiente reborde:
     - Si el intervalo es de perfil bajo ($\approx 1x$) $\rightarrow$ Clasificar como **Canasta Pequeña**.
     - Si el intervalo es de perfil alto ($\approx 2x$, aprox. el doble de una pequeña) con nervaduras $\rightarrow$ Clasificar como **Canasta Grande**.

4. **Tratamiento del Anidamiento (Nesting)**:
   - Las canastas encajan parcialmente unas dentro de otras al apilarse.
   - El conteo exacto se basa en el número de rebordes perimetrales y ranuras de agarre, no en la altura externa total del conjunto.

5. **Consolidación de Totales**:
   - $\text{Total Canastas} = \sum \text{Canastas Pequeñas} + \sum \text{Canastas Grandes}$.
   - Funciona para cualquier cantidad $N \ge 1$.

---

## 3. Esquema de Respuesta Estructurado

El análisis visual debe devolver siempre el conteo consolidado dinámico:

```json
{
  "total": 14,
  "canastas_pequenas": 8,
  "canastas_grandes": 6,
  "columnas_detectadas": 1,
  "desglose_niveles": [
    {"nivel": 1, "tipo": "grande", "posicion": "superior"},
    {"nivel": 2, "tipo": "pequena", "posicion": "nivel 2"},
    {"nivel": 3, "tipo": "pequena", "posicion": "nivel 3"}
    // ... hasta el nivel N
  ],
  "confianza": "alta",
  "descripcion": "Pila vertical de 14 canastas (6 grandes y 8 pequeñas) identificadas por rebordes de encaje y proporción 2:1."
}
```
