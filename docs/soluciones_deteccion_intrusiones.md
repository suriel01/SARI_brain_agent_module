# 🎯 SARI — Análisis y Soluciones: Definición Inteligente de Intrusión Perimetral

**Documento**: `doc/soluciones_deteccion_intrusiones.md`  
**Estado**: Análisis Técnico & Propuestas de Solución  
**Objetivo**: Transformar la simple detección genérica de personas (`class: person` en YOLO) en un motor robusto de clasificación de intrusiones y evaluación de amenazas en tiempo real.

---

## 1. El Problema Actual

Actualmente, el módulo de visión en la Jetson ejecuta un modelo YOLO que detecta cajas delimitadoras (*bounding boxes*) de la clase `person`.
- **Falso positivo de intrusión**: Un transeúnte caminando por la banqueta pública fuera de la reja, un operador de mantenimiento autorizado con uniforme durante el día, o una persona visible a través de una ventana.
- **Falso negativo de riesgo**: Alguien agachado forzando una cerradura, escalando una barda perimetral o merodeando en un punto ciego durante la madrugada.

Detectar a un "humano" no equivale a detectar una "intrusión". La intrusión se define por **dónde está**, **hacia dónde se mueve**, **cuánto tiempo permanece**, **qué postura adopta**, **en qué horario ocurre** y **qué objetos porta**.

---

## 2. Soluciones Técnicas Recomendadas

A continuación se presentan 7 soluciones estructuradas de menor a mayor complejidad para implementar en el ecosistema SARI:

```
                  ┌──────────────────────────────────────────────┐
                  │          ENTRADA: DETECCIÓN YOLO             │
                  │             (Persona Detectada)              │
                  └──────────────────────┬───────────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
┌───────────────┐               ┌────────────────┐               ┌────────────────┐
│ 1. Geofencing │               │ 2. Permanencia │               │ 3. Ventana     │
│  & Tripwires  │               │  (Loitering)   │               │   Horaria      │
│  ¿Cruzó barda?│               │  ¿> 8 segundos?│               │ ¿Madrugada?    │
└───────┬───────┘               └────────┬───────┘               └────────┬───────┘
        │                                │                                │
        └────────────────────────────────┼────────────────────────────────┘
                                         ▼
                        ┌─────────────────────────────────┐
                        │   CALCULADORA DE AMENAZA (0-100)│
                        │   • Poses de riesgo (YOLO-Pose) │
                        │   • Objetos (Escalera, Armas)   │
                        │   • Sensores físicos (Tamper)   │
                        └────────────────┬────────────────┘
                                         ▼
                        ┌─────────────────────────────────┐
                        │     ¿Puntaje de Riesgo > 75?    │
                        │   SI ──> 🚨 DISPARO DE ALARMA   │
                        │   NO ──> 📝 Registro Bitácora   │
                        └─────────────────────────────────┘
```

---

### Solución 1: Geocercas y Cruce de Líneas Virtuales (Tripwires & Polígonos)
> **Dificultad**: Baja - Media | **Impacto**: Inmediato | **Carga computacional**: Mínima (< 2% CPU)

- **Concepto**:
  Sobre la imagen de la cámara se configuran dos entidades geométricas:
  1. **Polígono de Exclusión (Zona Prohibida)**: Área que comprende el interior de las instalaciones o el pasillo pegado a la cerca. Si el punto central de los pies del humano (`bbox_bottom_center`) cae dentro del polígono, es considerado zona caliente.
  2. **Línea de Traspaso Unidireccional (*Tripwire*)**: Una línea virtual dibujada sobre la barda con dirección vectorial ($A \rightarrow B$). Si la trayectoria del humano cruza de "Exterior" hacia "Interior", se dispara alarma inmediata. Si se mueve de adentro hacia afuera, no genera alarma o genera alerta de salida.
- **Implementación**:
  Uso del algoritmo *Point-in-Polygon* (`shapely` o `cv2.pointPolygonTest`).
- **Ventaja**: Elimina el 90% de falsas alarmas provocadas por personas caminando por la calle o acera pública.

---

### Solución 2: Merodeo Temporal (*Loitering Detection*)
> **Dificultad**: Baja | **Impacto**: Alto | **Carga computacional**: Mínima

- **Concepto**:
  Una persona que camina rápidamente por el perímetro no representa una amenaza inminente; alguien que se queda estático observando o esperando frente a la barda por más de $N$ segundos (ej. 10 segundos) se considera en **fase de reconocimiento/intrusión**.
- **Implementación**:
  - Emplear un tracker ligero en la Jetson (**ByteTrack** o **BoT-SORT**, ya integrados en Ultralytics YOLO).
  - Cada persona recibe un `track_id` persistente.
  - El sistema calcula:
    $$\Delta t = t_{\text{actual}} - t_{\text{primer\_avistamiento}}$$
  - Si $\Delta t > 8\text{ s}$ dentro del radio perimetral $\rightarrow$ Se escala a **Alerta de Merodeo Sospechoso**.

---

### Solución 3: Matrices Horarias y Perfiles de Amenaza Táctica
> **Dificultad**: Muy Baja | **Impacto**: Alto | **Carga computacional**: Nula

- **Concepto**:
  El contexto horario cambia radicalmente el significado de una detección humana:
  - **Modo Diurno / Operativo (07:00 - 19:00)**: Se permite circulación general; solo se alerta si hay cruce estricto de tripwires o apertura de portón sin tarjeta.
  - **Modo Táctico Nocturno (22:00 - 06:00)**: **Cero tolerancia**. Cualquier ser humano detectado en el campo de visión de la cámara activa de inmediato la alerta crítica a Telegram y pre-enciende reflectores/sirena de disuasión.
- **Implementación**:
  Regla condicional de políticas en el script de la Jetson y en el backend de SARI.

---

### Solución 4: Detección de Objetos Críticos Asociados
> **Dificultad**: Media | **Impacto**: Muy Alto | **Carga computacional**: Baja

- **Concepto**:
  Entrenar o configurar clases adicionales en el modelo YOLO de la Jetson para detectar objetos que acompañan a un intruso:
  - **Escaleras portátiles**: Preparación para brincar barda.
  - **Herramientas de corte / cizallas / palancas**: Sabotaje de cerraduras y malla ciclónica.
  - **Mochilas tácticas voluminosas**: Potencial extracción de bienes o transporte de equipo.
  - **Objetos punzocortantes / armas de fuego**.
  - **Rostros cubiertos (pasamontañas, capuchas completas)**.
- **Lógica**:
  $$\text{Persona} + \text{Escalera/Herramienta} \implies \text{Intrusión Crítica (Riesgo 100\%) } \rightarrow \text{Alarma instantánea}$$

---

### Solución 5: Análisis de Poses y Actitudes Anómalas (YOLOv8-Pose)
> **Dificultad**: Media - Alta | **Impacto**: Excepcional | **Carga computacional**: Media (+ 15-20% GPU)

- **Concepto**:
  En lugar de solo detectar una caja rectangular, **YOLO-Pose** detecta 17 puntos clave del esqueleto humano (tobillos, rodillas, caderas, muñecas, hombros, cabeza).
- **Firmas cinemáticas de intrusión**:
  1. **Escalamiento de Muros**: Pies y manos a una elevación anormal respecto al suelo, centro de gravedad elevado cerca del borde superior de la barda.
  2. **Reptado o Avance Pecho a Tierra**: Vector columna-cadera horizontal a menos de 40 cm del suelo (intentando evadir sensores infrarrojos).
  3. **Manos Ocultas o Manipulando Cerradura**: Muñecas juntas a la altura de la chapa o candado por más de 5 segundos.
  4. **Postura de Carrera / Fuga**: Ángulo de inclinación del torso $> 25^\circ$ con zancadas de alta velocidad.

---

### Solución 6: Fusión Sensorial con Hardware Anti-Tamper
> **Dificultad**: Media | **Impacto**: Máxima fiabilidad física | **Carga computacional**: Nula

- **Concepto**:
  Integrar la visión por computadora con la electrónica que desarrollará el equipo:
  - Si la cámara ve una persona cerca de la barda **Y AL MISMO TIEMPO** el sensor de vibración de la barda (acelerómetro MPU6050 o sensor piezoeléctrico de malla) registra impactos $\implies$ **Intrusión física confirmada**.
  - Si la cámara detecta una persona cerca de la Jetson **Y** el acelerómetro de la cámara registra que la están intentando mover $\implies$ **Sabotaje a la cámara**.

---

### Solución 7: Clasificación Semántica con Modelos VLM Ligeros en Backend
> **Dificultad**: Media | **Impacto**: Inteligencia de Alto Nivel | **Carga computacional**: Ejecutada en Host (RTX 4070)

- **Concepto**:
  Cuando la Jetson detecta una persona en zona perimetral, envía el fotograma al Backend de SARI Cerebro. En el backend, un modelo de Visión-Lenguaje local (como **Moondream2**, **Qwen2-VL 2B** o **MiniCPM-V**) analiza la escena respondiendo preguntas tácticas en 150 ms:
  - *Prompt*: `"Describe briefly the person in this security camera: are they climbing, breaking in, wearing security gear, or just passing by?"`
  - La respuesta del modelo se pasa a NeMo Guardrails para generar un informe pericial automático en el hilo de chat del SOC.

---

## 3. Hoja de Ruta Recomendada para Implementación

1. **Fase 1 (Inmediata y Sin Costo de GPU)**:
   - Configurar **Geocercas poligonales** y **Líneas de cruce (Tripwires)** en el script de la Jetson.
   - Activar el **Tracker (ByteTrack)** para calcular tiempo de permanencia (**Loitering > 8 segundos**).
   - Aplicar el **Filtro Horario Nocturno** (alta sensibilidad nocturna).
2. **Fase 2 (Próximo Sprint con Electrónica)**:
   - Fusión sensorial con sensores de contacto de puerta y vibración de barda.
3. **Fase 3 (IA Avanzada)**:
   - Implementar YOLO-Pose para posturas de escalamiento y análisis VLM en el backend.
