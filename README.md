# El Fanatico

App de noticias deportivas que se actualiza sola cada ~10 min y te avisa de lo viral.

## Puesta en marcha (una sola vez, ~10 min)
1. En GitHub crea un repositorio **público** y sube todo el contenido de esta carpeta (incluida `.github`).
2. En el repo: **Settings → Pages → Source: GitHub Actions**.
3. En tu Android instala la app **ntfy** (Play Store) y suscríbete a un tema largo e inventado, por ejemplo `elfanatico-x7k29qpm`.
4. En el repo: **Settings → Secrets and variables → Actions → New secret**: nombre `NTFY_TOPIC`, valor = ese tema.
5. Pestaña **Actions → Actualizar El Fanatico → Run workflow**. Al terminar, tu app queda en `https://TU_USUARIO.github.io/NOMBRE_DEL_REPO/`.
6. Abre esa dirección en Chrome (Android) → menú ⋮ → **Instalar app**.

## Personalizar
- `feeds.json`: añade o quita fuentes RSS. Si una falla, se omite sin romper nada.
- Reporteros: añade cuentas de Bluesky en `"bluesky"`, por ejemplo `{"sport":"basket","handle":"usuario.bsky.social","name":"Nombre"}`. X no ofrece acceso gratuito a sus publicaciones.
- Tendencia (🔥): la misma historia en 3 o más fuentes, o palabra clave (breaking, traded, lesión…) en 2 o más, o en un reportero.

## Límites
GitHub puede retrasar la ejecución programada unos minutos. Si el repo queda 60 días sin actividad tuya, GitHub pausa las tareas programadas: entra a Actions y reactívalas.

## Marcadores y carruseles
- Pestaña 🏟️ Marcadores: resultados y calendario (ayer, hoy, mañana) con datos públicos de ESPN. Las ligas se editan en `feeds.json`, sección `"scores"`.
- Botón 🎠 Crear carrusel: arma láminas listas para publicar (Top del día, por deporte o marcadores de una liga) y las descarga en un ZIP.
