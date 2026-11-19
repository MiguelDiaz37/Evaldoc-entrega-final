document.addEventListener("input", function (evento) {
  const campo = evento.target;
  if (!campo.matches("textarea[data-contador]")) return;
  const contenedor = campo.closest("form");
  const largo = campo.value.trim().length;
  const cuenta = contenedor.querySelector("[data-cuenta]");
  if (cuenta) {
    cuenta.textContent = campo.value.length;
    const maximo = Number(campo.getAttribute("maxlength") || 0);
    cuenta.parentElement.classList.toggle("mal", maximo > 0 && campo.value.length > maximo);
  }
  const minimo = Number(campo.dataset.minimo || 0);
  const envio = contenedor.querySelector("[data-envio]");
  if (envio && minimo) envio.disabled = largo < minimo;
});

document.addEventListener("change", function (evento) {
  const radio = evento.target;
  if (radio.name !== "puntaje") return;
  const selector = radio.closest("[data-selector-estrellas]");
  const texto = selector && selector.querySelector("[data-texto-nota]");
  if (!texto) return;
  const etiqueta = selector.querySelector('label[for="' + radio.id + '"]');
  texto.textContent = radio.value && etiqueta ? etiqueta.dataset.texto : "Sin calificación";
});
