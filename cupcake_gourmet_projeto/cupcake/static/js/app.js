"use strict";

// Melhoria progressiva: tudo continua navegável se o JavaScript estiver desativado.
const menuButton = document.querySelector(".menu-toggle");
const mainNav = document.getElementById("main-nav");
if (menuButton && mainNav) {
  menuButton.addEventListener("click", () => {
    const opened = mainNav.classList.toggle("is-open");
    menuButton.setAttribute("aria-expanded", String(opened));
  });
}

const search = document.querySelector("[data-search]");
if (search) {
  const cards = [...document.querySelectorAll("[data-product]")];
  const empty = document.getElementById("sem-resultado");
  search.addEventListener("input", () => {
    const query = search.value.toLocaleLowerCase("pt-BR").trim();
    let count = 0;
    for (const card of cards) {
      const visible = card.dataset.product.includes(query);
      card.hidden = !visible;
      if (visible) count += 1;
    }
    if (empty) empty.hidden = count > 0;
  });
}

const addressGroup = document.querySelector("[data-address-group]");
const deliveryOptions = document.querySelectorAll('input[name="modalidade"]');
function refreshAddress() {
  if (!addressGroup) return;
  const delivery = document.querySelector('input[name="modalidade"]:checked')?.value === "ENTREGA";
  addressGroup.hidden = !delivery;
  const field = addressGroup.querySelector("textarea");
  if (field) field.required = delivery;
}
deliveryOptions.forEach(option => option.addEventListener("change", refreshAddress));
refreshAddress();
