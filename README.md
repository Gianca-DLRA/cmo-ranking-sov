# Enfoque metodológico

El modelo propuesto parte de la premisa de que el SOV es un fenómeno multidimensional que incluye:

* **Oferta de contenido** (lo que publican los equipos)
* **Respuesta de la audiencia** (cómo interactúan los usuarios)
* **Demanda de información** (interés activo de búsqueda)
* **Cobertura mediática** (presencia en medios y conversación externa)

Dado lo anterior, el SOV total se define como una combinación ponderada de cuatro componentes:

$$
SOV_{total} = w_1(SOV_{engagement}) + w_2(SOV_{menciones}) + w_3(SOV_{search}) + w_4(SOV_{media})
$$

# Componentes del modelo

## 1. SOV de engagement (40%)

Este componente mide la proporción del engagement total generado por cada equipo dentro del ecosistema analizado.

$$
SOV_{engagement} = \frac{\text{engagement total del equipo}}{\text{engagement total de todos los equipos}}
$$

El engagement incluye interacciones como "likes", comentarios, compartidos y visualizaciones en plataformas sociales.

**Fuente de datos:**

* Instagram
* TikTok

**Justificación:**
Este componente captura la **capacidad del contenido para generar atención e interacción**, siendo uno de los indicadores más directos del impacto de la estrategia de marketing digital.

## 2. SOV de menciones (25%)

Este componente mide la proporción de menciones que recibe cada equipo dentro del total de la conversación digital.

$$
SOV_{menciones} = \frac{\text{menciones del equipo}}{\text{menciones totales}}
$$

Se consideran menciones en redes sociales, foros y otros espacios digitales públicos.

**Fuente de datos:**

* X (Twitter)
* Reddit

**Justificación:**
Refleja el **nivel de presencia espontánea en la conversación**, incluyendo tanto contenido generado por usuarios como discusiones orgánicas.

## 3. SOV de búsqueda (25%)

Este componente mide la proporción del interés de búsqueda asociado a cada equipo.

$$
SOV_{search} = \frac{\text{interés de búsqueda del equipo}}{\text{interés total}}
$$

**Fuente de datos:**

* Google Trends

**Justificación:**
Captura la **demanda activa de información**, funcionando como un proxy del interés real del mercado más allá de la exposición pasiva.

## 4. SOV de cobertura mediática (10%)

Este componente mide la proporción de cobertura en medios digitales.

$$
SOV_{media} = \frac{\text{artículos o notas sobre el equipo}}{\text{total de artículos}}
$$

**Fuente de datos:**

* Medios deportivos digitales (scraping y agregadores de noticias)

**Justificación:**
Refleja la **visibilidad editorial y relaciones públicas**, un componente relevante en la construcción de marca.

# Justificación de los pesos

La asignación de pesos responde a criterios de relevancia estratégica y calidad de la señal:

* **Engagement (40%)**: Se prioriza por ser la métrica más directamente relacionada con la capacidad de generar interacción y atención efectiva.
* **Menciones (25%)**: Representa la amplitud de la conversación, aunque puede incluir ruido.
* **Search (25%)**: Captura intención e interés activo, complementando la medición de awareness.
* **Media (10%)**: Aporta contexto institucional y cobertura, aunque con menor frecuencia relativa.

Esta ponderación busca equilibrar:

* **Señales de oferta (contenido)**
* **Señales de respuesta (engagement)**
* **Señales de demanda (búsqueda)**
* **Señales de validación externa (medios)**

# Consideraciones metodológicas

* El modelo se construye exclusivamente con **fuentes públicas y observables**, garantizando replicabilidad.
* Se aplican procesos de limpieza y desambiguación para asegurar la correcta atribución de menciones.
* Los resultados representan una **estimación relativa del SOV**, no una medición absoluta.

Adicionalmente, dado que existen diferencias estructurales entre equipos (tamaño de la afición, historia, desempeño deportivo), los resultados deben interpretarse como una combinación de:

* desempeño de marketing
* posicionamiento histórico
* contexto competitivo
