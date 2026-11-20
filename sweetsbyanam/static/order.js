/* The order form: builds the item cards from the menu data, shows a running estimate, and sends the
   order to /api/orders as JSON. The server re-checks everything, so this script is for convenience. */
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("menu-data").textContent);
  var form = document.getElementById("order-form");
  var itemsBox = document.getElementById("items");
  var alertBox = document.getElementById("form-alert");
  var submitBtn = document.getElementById("submit");
  var counter = 0;

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "class") node.className = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { node.appendChild(c); });
    return node;
  }

  function select(id, options, placeholder) {
    var s = el("select", { id: id });
    s.appendChild(el("option", { value: "", text: placeholder || "Choose..." }));
    options.forEach(function (o) { s.appendChild(el("option", { value: o, text: o })); });
    return s;
  }

  function field(n, key, label, control, opts) {
    opts = opts || {};
    var wrap = el("div", { class: "field", "data-field": key });
    var lab = el("label", { for: control.id, text: label });
    if (opts.optional) lab.appendChild(el("span", { class: "opt", text: " (optional)" }));
    wrap.appendChild(lab);
    wrap.appendChild(control);
    if (opts.help) wrap.appendChild(el("p", { class: "help", text: opts.help }));
    wrap.appendChild(el("p", { class: "err", "data-err": "items." + n + "." + key }));
    return wrap;
  }

  function addItem(focus) {
    var n = counter++;
    var card = el("div", { class: "item-card", "data-item": String(n) });
    var id = function (s) { return "it" + n + "-" + s; };

    var head = el("div", { class: "item-card-head" });
    head.appendChild(el("p", { class: "item-title", text: "Item" }));
    var remove = el("button", { type: "button", class: "link-btn", text: "Remove" });
    head.appendChild(remove);
    card.appendChild(head);

    var productSel = el("select", { id: id("product") });
    productSel.appendChild(el("option", { value: "", text: "Choose an item..." }));
    [["treats", "Treats"], ["packs", "Party packs"]].forEach(function (g) {
      var og = el("optgroup", { label: g[1] });
      Object.keys(data.products).forEach(function (k) {
        var p = data.products[k];
        if (p.group === g[0]) og.appendChild(el("option", { value: k, text: p.name + " (" + p.price + ")" }));
      });
      productSel.appendChild(og);
    });
    card.appendChild(field(n, "product", "Item", productSel));

    var body = el("div", { class: "item-body-fields" });
    card.appendChild(body);
    card.appendChild(el("p", { class: "err", "data-err": "items." + n }));

    productSel.addEventListener("change", function () { renderFields(n, body, productSel.value); updateEstimate(); });
    remove.addEventListener("click", function () { card.remove(); renumber(); updateEstimate(); });
    itemsBox.appendChild(card);
    renumber();
    if (focus === true) productSel.focus();
  }

  function renumber() {
    var cards = itemsBox.querySelectorAll(".item-card");
    cards.forEach(function (c, i) { c.querySelector(".item-title").textContent = "Item " + (i + 1); });
    itemsBox.querySelectorAll(".link-btn").forEach(function (b) { b.hidden = cards.length < 2; });
  }

  function renderFields(n, body, key) {
    body.textContent = "";
    if (!key) return;
    var p = data.products[key];
    var id = function (s) { return "it" + n + "-" + s; };

    var lo = p.limits[0], hi = p.limits[1];
    var qty = el("select", { id: id("qty") });
    for (var q = lo; q <= hi; q++) {
      var label = q + " " + (q === 1 ? p.unit_label[0] : p.unit_label[1]);
      qty.appendChild(el("option", { value: String(q), text: label }));
    }
    qty.addEventListener("change", updateEstimate);
    body.appendChild(field(n, "qty", p.unit === "dozen" ? "How many dozen?" : "How many?", qty));

    if (p.style === "combo_or_classic") {
      var modes = el("div", { class: "choices", role: "radiogroup", "aria-label": "Flavor style" });
      [["combo", "Signature combination"], ["classic", "Build your own"]].forEach(function (m, i) {
        var input = el("input", { type: "radio", name: "mode-" + n, value: m[0] });
        if (i === 0) input.checked = true;
        modes.appendChild(el("label", { class: "choice" }, [input, document.createTextNode(" " + m[1])]));
      });
      var comboWrap = el("div", { class: "mode-combo" });
      var combo = select(id("combo"), Object.keys(data.combos), "Choose a combination...");
      var comboHelp = el("p", { class: "help", text: "" });
      combo.addEventListener("change", function () { comboHelp.textContent = data.combos[combo.value] || ""; });
      comboWrap.appendChild(field(n, "combo", "Combination", combo));
      comboWrap.appendChild(comboHelp);
      var classicWrap = el("div", { class: "mode-classic" });
      classicWrap.hidden = true;
      classicWrap.appendChild(field(n, "cake", "Cake flavor", select(id("cake"), data.cake_flavors)));
      classicWrap.appendChild(field(n, "frosting", "Frosting flavor", select(id("frosting"), data.frostings)));
      modes.addEventListener("change", function () {
        var classic = modes.querySelector("input:checked").value === "classic";
        comboWrap.hidden = classic; classicWrap.hidden = !classic;
      });
      var modeField = el("div", { class: "field" }, [el("span", { class: "label", text: "Flavors" }), modes,
                         el("p", { class: "err", "data-err": "items." + n + ".mode" })]);
      body.appendChild(modeField); body.appendChild(comboWrap); body.appendChild(classicWrap);
    }

    p.fields.forEach(function (f) {
      var control;
      if (f.options) control = select(id(f.key), f.options);
      else if (f.kind === "textarea") control = el("textarea", { id: id(f.key), rows: "3", maxlength: "1000" });
      else control = el("input", { id: id(f.key), maxlength: "120", type: "text" });
      body.appendChild(field(n, f.key, f.label, control, { optional: !f.required, help: f.help }));
    });
    body.appendChild(field(n, "notes", "Notes for this item", el("textarea", { id: id("notes"), rows: "2", maxlength: "500" }),
      { optional: true, help: "Theme, colors, decorations, packaging..." }));
  }

  function collectItem(card) {
    var n = card.getAttribute("data-item");
    var get = function (s) { var e = document.getElementById("it" + n + "-" + s); return e ? e.value : ""; };
    var key = get("product");
    var item = { product: key };
    if (!key) return item;
    var p = data.products[key];
    item.qty = parseInt(get("qty"), 10);
    if (p.style === "combo_or_classic") {
      var mode = card.querySelector('input[name="mode-' + n + '"]:checked').value;
      item.mode = mode;
      if (mode === "combo") item.combo = get("combo");
      else { item.cake = get("cake"); item.frosting = get("frosting"); }
    }
    p.fields.forEach(function (f) { item[f.key] = get(f.key); });
    item.notes = get("notes");
    return item;
  }

  function money(cents) { return "$" + (cents / 100).toLocaleString("en-US"); }

  function updateEstimate() {
    var total = 0, plus = false;
    itemsBox.querySelectorAll(".item-card").forEach(function (card) {
      var n = card.getAttribute("data-item");
      var key = document.getElementById("it" + n + "-product").value;
      var qtyEl = document.getElementById("it" + n + "-qty");
      if (!key || !qtyEl) return;
      var p = data.products[key];
      total += p.price_cents * parseInt(qtyEl.value, 10);
      plus = plus || p.plus;
    });
    document.getElementById("estimate").textContent = money(total) + (plus ? "+" : "");
    document.getElementById("estimate-note").textContent = plus ? "(some items start at this price)" : "";
  }

  function clearErrors() {
    form.querySelectorAll(".err").forEach(function (e) { e.textContent = ""; });
    form.querySelectorAll("[aria-invalid]").forEach(function (e) { e.removeAttribute("aria-invalid"); });
    alertBox.hidden = true;
  }

  function showErrors(fields, message) {
    var first = null;
    Object.keys(fields || {}).forEach(function (key) {
      var target = form.querySelector('[data-err="' + key + '"]');
      if (target) {
        target.textContent = fields[key];
        var wrap = target.closest(".field");
        var control = wrap && wrap.querySelector("input, select, textarea");
        if (control) control.setAttribute("aria-invalid", "true");
        if (!first) first = control || target;
      }
    });
    alertBox.textContent = message || "Please fix the highlighted fields.";
    alertBox.hidden = false;
    alertBox.focus();
    if (first && first.focus) first.focus();
  }

  // As soon as someone edits a field, its old error message goes away.
  function clearFieldError(ev) {
    if (ev.target.id === "photos") return;  // the photo picker writes its own messages
    var wrap = ev.target.closest && ev.target.closest(".field");
    if (!wrap) return;
    wrap.querySelectorAll(".err").forEach(function (e) { e.textContent = ""; });
    wrap.querySelectorAll("[aria-invalid]").forEach(function (e) { e.removeAttribute("aria-invalid"); });
  }
  form.addEventListener("input", clearFieldError);
  form.addEventListener("change", clearFieldError);

  // ---- inspiration photos: collect up to 5, show small previews, let the customer remove any
  var MAX_PHOTOS = 5, MAX_BYTES = 5 * 1024 * 1024;
  var photos = [];
  var photoInput = document.getElementById("photos");
  var thumbs = document.getElementById("thumbs");
  var photoErr = form.querySelector('[data-err="images"]');

  function okType(f) { return /^image\/(jpeg|png|webp)$/.test(f.type) || /\.(jpe?g|png|webp)$/i.test(f.name); }

  function renderPhotos() {
    thumbs.textContent = "";
    photos.forEach(function (f, i) {
      var li = el("li");
      var img = el("img", { alt: "Preview of " + f.name });
      img.src = URL.createObjectURL(f);
      var rm = el("button", { type: "button", class: "link-btn", text: "Remove" });
      rm.setAttribute("aria-label", "Remove " + f.name);
      rm.addEventListener("click", function () { URL.revokeObjectURL(img.src); photos.splice(i, 1); photoErr.textContent = ""; renderPhotos(); });
      li.appendChild(img);
      li.appendChild(el("span", { class: "thumb-name", text: f.name }));
      li.appendChild(rm);
      thumbs.appendChild(li);
    });
  }

  photoInput.addEventListener("change", function () {
    var messages = [];
    Array.prototype.forEach.call(photoInput.files, function (f) {
      if (!okType(f)) messages.push("'" + f.name + "' isn't a JPG, PNG or WebP photo.");
      else if (f.size > MAX_BYTES) messages.push("'" + f.name + "' is larger than 5 MB.");
      else if (photos.length >= MAX_PHOTOS) messages.push("You can attach up to " + MAX_PHOTOS + " photos.");
      else photos.push(f);
    });
    photoInput.value = "";  // so the same photo can be picked again after removing it
    renderPhotos();
    photoErr.textContent = messages.join(" ");
  });

  var delivery = form.querySelectorAll('input[name="fulfilment"]');
  delivery.forEach(function (r) {
    r.addEventListener("change", function () {
      var on = form.querySelector('input[name="fulfilment"]:checked').value === "delivery";
      document.getElementById("address-field").hidden = !on;
    });
  });
  document.getElementById("add-item").addEventListener("click", function () { addItem(true); });

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    clearErrors();
    var payload = {
      name: form.name.value, email: form.email.value, phone: form.phone.value,
      event_date: form.event_date.value, occasion: form.occasion.value,
      fulfilment: form.querySelector('input[name="fulfilment"]:checked').value,
      address: form.address.value, allergies: form.allergies.value, notes: form.notes.value,
      website: form.website.value,
      items: Array.prototype.map.call(itemsBox.querySelectorAll(".item-card"), collectItem)
    };
    submitBtn.disabled = true;
    submitBtn.textContent = "Sending...";
    var body = new FormData();  // order details as JSON text, photos as files
    body.append("order", JSON.stringify(payload));
    photos.forEach(function (f) { body.append("images", f, f.name); });
    fetch("/api/orders", { method: "POST", body: body }).then(function (res) {
      return res.json().then(function (body) { return { status: res.status, body: body }; });
    }).then(function (r) {
      if (r.status === 201) { window.location.href = r.body.redirect; return; }
      var err = (r.body && r.body.error) || {};
      showErrors(err.fields, err.message || "Something went wrong. Please try again.");
      submitBtn.disabled = false; submitBtn.textContent = "Send my order request";
    }).catch(function () {
      showErrors({}, "We couldn't send your order. Check your connection and try again, or email us instead.");
      submitBtn.disabled = false; submitBtn.textContent = "Send my order request";
    });
  });

  addItem(false);
  var firstProduct = document.getElementById("it0-product");
  var params = new URLSearchParams(window.location.search);
  if (params.get("item") && data.products[params.get("item")]) {
    firstProduct.value = params.get("item");
    firstProduct.dispatchEvent(new Event("change"));
  }
})();
