(function () {
  function initFormEmbeds() {
    var scripts = document.querySelectorAll('script[data-form-id]');
    scripts.forEach(function (script) {
      if (script.dataset.formEmbedInitialized === 'true') {
        return;
      }

      var formId = script.getAttribute('data-form-id');
      if (!formId) {
        return;
      }

      var iframe = document.createElement('iframe');
      iframe.src = '/f/' + encodeURIComponent(formId);
      iframe.width = script.getAttribute('data-width') || '100%';
      iframe.height = script.getAttribute('data-height') || '760';
      iframe.style.border = '0';
      iframe.style.maxWidth = '100%';
      iframe.setAttribute('loading', 'lazy');
      iframe.setAttribute('title', 'Embedded CRM Form');

      script.parentNode.insertBefore(iframe, script.nextSibling);
      script.dataset.formEmbedInitialized = 'true';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFormEmbeds);
  } else {
    initFormEmbeds();
  }
})();
