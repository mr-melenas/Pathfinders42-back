# Índice lunar v0.3: roca volcánica desnuda análoga a los mares basálticos

Qué detecta: roca volcánica desnuda y pobre en cuarzo, análoga a los mares basálticos de la Luna.

Índice de satélite: percentil del índice máfico MI = e9.1/e10.6 (emisividad térmica CAMEL v003, celdas de 0,05°) dentro del dominio desnudo. Dominio: nieve < 0,10; NDVI mediano anual < 0,15; NDVI del mes de la emisividad < 0,15; índice de cuarzo CI = e10.6/e11.3 ≤ 1,008. Las regiones candidatas son zonas contiguas por encima del percentil 95 (al menos 10 celdas) con al menos un 50 % de roca volcánica según el mapa litológico GLiM; GLiM filtra pero no puntúa.

Validación: los análogos lunares verificados (Craters of the Moon, Kīlauea, Pinacate, Askja, Lanzarote) tienen percentil mediano 97,4; seis campos volcánicos de prueba ciega (Al Haruj, Khaybar, Rahat, Hoggar, Payún, Holuhraun), 92,6; las arenas de cuarzo de control, 13,2. AUC 0,96 (análogos frente a controles) y 1,00 (volcánicos frente a controles). En las celdas ≥ p95 hay 7 veces más basalto que en el dominio.

Candidatas principales: Afar (Etiopía), Harrat ash-Shaam (Siria), harrats de Medina, La Meca y Tabuk (Arabia Saudí), Marsabit y Turkana (Kenia), Ódáðahraun (Islandia), Tibesti (Chad), Kunene/Etendeka (Namibia), Lahij (Yemen) e Irán.

Limitaciones: Kīlauea puntúa bajo (p48) por los recubrimientos de sílice opalina de sus coladas (Kraft et al., 2003; Seelos et al., 2010). Carbonatos y salinas también suben en el 10 % superior, por eso se filtra con GLiM. Celdas de unos 5 km. El índice representa los mares basálticos, no el polo sur lunar (tierras altas de anortosita, sombra permanente, hielo).
