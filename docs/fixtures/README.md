# Fixtures de tickets

Cada caso va en `receipts/<caso>/` con las fotos y un `gt.json`. Los tests lo descubren solos.

## Antes de agregar un ticket

Lo que entra en un commit queda en el historial aunque después se borre, así que esto se hace
antes de `git add`. Guardá los originales fuera del repo.

1. Mirá la foto completa y anotá los datos personales: nombre, RUC o cédula del comprador,
   usuario del cajero, número de factura, teléfono, tarjeta, código QR o de la factura electrónica.
2. Tapalos y quitá los metadatos. Las coordenadas son de la imagen ya orientada:

   ```sh
   uv run --script docs/fixtures/sanitize_image.py original.jpg receipts/<caso>/img1.jpg \
       --box x0,y0,x1,y1
   ```

3. Abrí el resultado y comprobá que no se lea nada de lo tapado.
4. Reemplazá esos mismos valores por `[REDACTADO]` en `gt.json`.
5. Buscá los valores originales en todo el repo y corré `uv run pytest` en `api/`.

El test `api/tests/test_fixture_privacy.py` falla si una foto tiene EXIF, pero no lee el contenido
de la imagen: los pasos 1 y 3 son visuales y no se pueden omitir.

## Qué se conserva

Datos del comercio (razón social, RUC, timbrado, dirección), fecha, productos y montos: son lo que
el OCR debe extraer. Muestran qué se compró, dónde y cuándo; por eso conviene que el repo sea privado.
