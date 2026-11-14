# Lista de Tareas — Implementación Spec 003 (Módulo Ojos / Eyes)

> **Regla de Ejecución (Constitución Art. 2 & 4)**: Implementar una tarea a la vez. Primero pruebas/validación, luego código. No avanzar a la siguiente sin verificar la actual.

---

### Fase 1: Persistencia y API Backend para Ojos
- [x] **T1.1**: Escribir test de integración `tests/test_eyes_crud.py` que valide CRUD de nodos Ojos y prueba de conexión. *(Cubre: RF-UB-02, Constitución Art. 4)*
- [x] **T1.2**: Crear modelo ORM `EyeNode` en `backend/app/models/models.py` y schemas en `schemas.py`. *(Cubre: RF-UB-02, CA-2)*
- [x] **T1.3**: Implementar router `backend/app/routers/eyes.py` con endpoints CRUD y verificación de conexión. *(Cubre: RF-UB-02, RF-UB-03)*
- [x] **T1.4**: Conectar el router en `backend/app/main.py` y crear el nodo inicial `Jetson-PTZ_1`. *(Cubre: CA-3)*
- [x] **T1.5**: Ejecutar `pytest tests/test_eyes_crud.py` y verificar resultado en verde. *(Cubre: CA-2, CA-3)*

### Fase 2: Internacionalización y Navegación Frontend
- [x] **T2.1**: Actualizar `sari-ui/src/i18n/translations.ts` con 'Ojos' / 'Eyes' y todas las etiquetas del nuevo módulo. *(Cubre: RF-UB-01, CA-1)*
- [x] **T2.2**: Modificar `sari-ui/src/components/Dashboard.tsx` para reflejar el nuevo nombre en la barra lateral y cabecera. *(Cubre: RF-UB-01, CA-1)*

### Fase 3: Componente Principal 'EyesModule'
- [x] **T3.1**: Crear `sari-ui/src/components/EyesModule.tsx` con el selector horizontal de nodos Ojos (chips interactivos con estado ONLINE/STANDBY). *(Cubre: RF-EV-01)*
- [x] **T3.2**: Implementar el visor de video central con HUD táctico, controles de orientación y botón interactivo REC (grabación en vivo con `MediaRecorder`). *(Cubre: RF-EV-02, RF-SD-01)*
- [x] **T3.3**: Implementar la tarjeta lateral de telemetría táctica del Ojo seleccionado (NPU, RAM, Temp, FPS, Wi-Fi/USB). *(Cubre: RF-UB-03)*
- [x] **T3.4**: Integrar la sección inferior de 'Historial de Grabaciones y Evidencias'. *(Cubre: RF-EV-04, CA-5)*

### Fase 4: Modal de Conexión y Emparejamiento de Nuevos Ojos
- [x] **T4.1**: Crear componente `sari-ui/src/components/ConnectEyeModal.tsx` con formulario validado, botón 'Probar Conexión' y pestaña de 'Comando de Instalación'. *(Cubre: RF-EV-03, CA-4)*
- [x] **T4.2**: Conectar el modal con el backend `/api/eyes` para refresco en caliente de la lista de cámaras. *(Cubre: CA-4)*

### Fase 5: Validación E2E y Walkthrough
- [x] **T5.1**: Probar en navegador la conmutación entre idiomas (ES/EN), la grabación de video REC y la persistencia de un nuevo nodo.
- [x] **T5.2**: Capturar evidencias visuales y generar walkthrough.
