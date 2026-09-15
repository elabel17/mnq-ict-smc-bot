# Herramientas web (Artifacts)

Fuente versionada de las paginas publicadas como Claude Artifacts. La data
real (notas, flags, entradas manuales) vive en la base de datos del
artifact publicado, no en estos archivos ni en este repo -- se accede
desde cualquier PC con el mismo link, sesion iniciada.

- `variante_f_chart.html` -- auditoria visual de las 55 operaciones de la
  variante F (union+FVG, sin edad, liquidez a favor) sobre velas de 15m
  reales. Notas y flags por operacion guardados en la coleccion `notes`.
  Publicado: https://claude.ai/artifact/MPEog4hW681bpFYwh8Cj51

- `registro_manual.html` -- registro de entradas manuales: clic en una vela,
  marca direccion/precio/motivo. Guardado en la coleccion `manual_trades`,
  para que Claude las lea y las cruce contra lo que detecta el motor.
  Publicado: https://claude.ai/artifact/BwCwC62ncXA17PFNxwGkeN

Si se edita el HTML fuente, hay que volver a publicarlo (Artifact tool) para
que el cambio llegue a la version en linea -- este repo solo guarda el
codigo, no lo sirve.
