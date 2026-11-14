# SARI — Especificación Técnica: Módulo de Autoprotección y Electrónica Anti-Tamper (Jetson Node)

**Documento**: `specs/005-hardware-tamper-autoprotection.md`  
**Estado**: Propuesta de Arquitectura para Implementación de Hardware  
**Autor**: Equipo SARI (Sistema Autónomo de Respuesta a Intrusiones)

---

## 1. Visión General del Subsistema de Electrónica

El subsistema de autoprotección convierte a cada nodo periférico **NVIDIA Jetson** en un centinela activo capaz de defender su propia integridad física y de datos frente a sabotajes perimetrales (corte de cable, impacto, vandalismo, apertura de chasis o robo de hardware).

```
 ┌─────────────────────────────────────────────────────────────┐
 │                NVIDIA JETSON (MÓDULO OJO)                  │
 │                                                             │
 │  [Sensores Tamper]                                          │
 │   ├── Acelerómetro I2C (MPU6050 / LIS3DH) ──> Vibración/Giro│
 │   ├── Switch Magnético / Reed ─────────────> Apertura Caja │
 │   ├── Sensor Voltaje ADC ──────────────────> Corte Fuente   │
 │   └── Termistor NTC / I2C ─────────────────> Sabotaje Térmico
 │                                                             │
 │  [Micro-Daemon en Rust (sari-tamper-daemon)]                │
 │   ├── Monitoreo de interrupciones GPIO en microsegundos     │
 │   ├── Disparo de reflejos locales inmediatos                │
 │   └── Publicación prioritaria MQTT (sari/nodes/{id}/tamper) │
 └──────────────────────────────┬──────────────────────────────┘
                                │ Wi-Fi / Ethernet
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                SARI CEREBRO & TELEGRAM SOC                  │
 │                                                             │
 │   ├── Activación de Sirenas Perimetrales 30s               │
 │   ├── Bloqueo Magnético de Accesos                         │
 │   └── Alerta Crítica Táctica a Operadores en Telegram      │
 └─────────────────────────────────────────────────────────────┘
```

---

## 2. Sensores Seleccionados y Conexión Hardware

### 2.1. Sensor de Impacto y Movimiento (IMU / Acelerómetro)
- **Modelo recomendado**: **MPU-6050** o **LIS3DH** (Bus I2C, pines 3 [SDA] y 5 [SCL] del header de 40 pines de la Jetson).
- **Función**:
  - Detectar vibraciones asociadas a golpes de martillo, taladro o intentos de arrancar la montura de la cámara.
  - Detectar cambios en la orientación espacial (desviación intencional del ángulo de visión de la cámara).

### 2.2. Sensor de Apertura de Gabinete (Tamper Switch)
- **Modelo recomendado**: **Microswitch de palanca normalmente cerrado (NC)** o **Sensor magnético Reed**.
- **Conexión**: Pin GPIO con resistencia pull-up interna/externa (interrupción de flanco ascendente).
- **Función**: Al abrir la tapa o carcasa de la cámara, el circuito se abre instantáneamente disparando la alerta de intrusión mecánica.

### 2.3. Supervisor de Alimentación y Batería de Respaldo
- **Componente**: Módulo supervisor de voltaje (o circuito divisor de tensión a convertidor ADC I2C como ADS1115).
- **Función**:
  - Detectar caída de la línea principal de 12V/19V.
  - Conmutar a celda LiFePO4 / Li-ion de respaldo (manteniendo a la Jetson viva entre 5 y 15 minutos para evacuar telemetría y evidencia).

---

## 3. Protocolo de Comunicación MQTT: Tópico Tamper

Cada evento detectado por la electrónica se publica en el broker Mosquitto con calidad de servicio **QoS 2 (Exactly Once)**:

### Tópico:
`sari/nodes/{node_id}/tamper`

### Payload JSON:
```json
{
  node_id: Jetson-PTZ_1,
  timestamp: 1789345200.12,
  tamper_type: enclosure_breach,
  severity: critical,
  details: {
    switch_chassis: OPEN,
    g_force_peak: 4.2,
    power_source: battery_backup,
    voltage_v: 11.2
  },
  local_actions_taken: [
    burst_evidence_capture,
    local_strobe_activated
  ]
}
```

Tipos de `tamper_type`:
1. `enclosure_breach`: Carcasa abierta.
2. `physical_impact`: Vibración o golpe severo detectado por el acelerómetro.
3. `angle_tamper`: Giro forzado del campo visual.
4. `power_loss`: Corte de energía comercial.
5. `thermal_critical`: Sobrecalentamiento extremo o intento de quemar la óptica.

---

## 4. Reflejos Autónomos Locales (Antes de Perder Red)

Si un intruso corta los cables de red o destruye la antena Wi-Fi, la Jetson debe ejecutar acciones reflejas de forma **100% autónoma y local**:

1. **Ráfaga de Evidencia Inmediata**: La cámara activa un hilo prioritario que toma 5 fotogramas consecutivos a máxima resolución y los almacena en memoria flash/NVMe protegida.
2. **Disuasión Local Inmediata**: Si la Jetson tiene conectado un buzzer piezoeléctrico de 110 dB o LED estroboscópico en un pin GPIO, lo enciende inmediatamente para espantar al perpetrador.
3. **Ceroización de Credenciales (Nivel Táctico Avanzado)**: Si el switch de apertura de carcasa es forzado y se confirma robo físico, la Jetson sobreescribe en memoria RAM los tokens JWT y claves privadas de acceso para evitar que el atacante extraiga llaves criptográficas del sistema.

---

## 5. Implementación del Daemon en Rust (`sari-tamper-daemon`)

### ¿Por qué Rust?
- **Garantía 24/7**: Cero fugas de memoria (*zero memory leaks*) y cero caídas por punteros nulos (`SIGSEGV`).
- **Bajo Consumo**: Menos de 4 MB de RAM en ejecución como servicio `systemd`.
- **Ecosistema**:
  - `rumqttc`: Cliente MQTT ultra-rápido y asíncrono con soporte de reconexión automática y LWT.
  - `tokio`: Concurrencia para manejar I2C, GPIO y red en paralelo.
  - `embedded-hal` / `linux-embedded-hal`: Acceso nativo al bus I2C de Linux `/dev/i2c-1` en la Jetson.

---

## 6. Próximos Pasos para el Equipo

1. [ ] **Fase 1**: Construir el prototipo en protoboard con switch reed y sensor MPU6050 conectado a los pines I2C y GPIO de la Jetson.
2. [ ] **Fase 2**: Escribir el daemon en Rust con lectura de aceleración e interrupción GPIO.
3. [ ] **Fase 3**: Añadir el handler de `sari/nodes/+/tamper` en `backend/app/mqtt/handlers.py` para reaccionar a eventos de autoprotección enviando notificación inmediata a Telegram y encendiendo la sirena central.
