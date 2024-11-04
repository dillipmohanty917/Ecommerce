import $ from 'jquery';
import 'materialize-css/dist/js/materialize';

import '../../dashboard/scss/dashboard.scss';

var supportsPassive = false;
try {
  var opts = Object.defineProperty({}, 'passive', {
    get: function() {
      supportsPassive = true;
    }
  });
  window.addEventListener('test', null, opts);
} catch (e) {}

function onScroll(func) {
  window.addEventListener('scroll', func, supportsPassive ? {passive: true} : false);
}

function openModal() {
  $('.modal-trigger-custom').on('click', function (e) {
    let that = this;
    $.ajax({
      url: $(this).data('href'),
      method: 'get',
      success: function (response) {
        let $modal = $($(that).attr('href'));
        $modal.html(response);
        initSelects();
        $modal.modal();
        let $captureTypeInput = $('.body-orders [name="mode"]');
        if ($captureTypeInput.length) {
          let $captureForms = $('.payment-capture-form');
          let $applyToCash = $('[name="payment-Cash"]').parents('.input');
          let $applyToCheque = $('[name="payment-Cheque"]').parents('.input');
          let onChange = () => {
            let type = $captureTypeInput.val();
            $applyToCash.toggleClass('hide', true);
            $applyToCheque.toggleClass('hide', true);
            $captureForms.each((index, form) => {
              let $form = $(form);
              let hideForm = $form.data('type') !== type;
              $form.toggleClass('hide', hideForm);
            });
          };
          $captureTypeInput.on('change', onChange);
          $captureTypeInput.trigger('change');
        }
      }
    });
    e.preventDefault();
  });
}

$(document).ready(function() {
  $('.modal').modal();
  openModal();
  $(document).on('submit', '.form-async', function(e) {
    let that = this;
    $.ajax({
      url: $(that).attr('action'),
      method: 'post',
      data: $(that).serialize(),
      complete: function(response) {
        if (response.status === 400) {
          $(that).parent().html(response.responseText);
          initSelects();
        } else {
          $('.modal-close').click();
        }
      },
      success: function(response) {
        if (response.redirectUrl) {
          window.location.href = response.redirectUrl;
        } else {
          location.reload();
        }
      }
    });
    e.preventDefault();
  }).on('click', '.modal-close', function() {
    $('.modal').modal('close');
  });

  function isTablet() {
    return !$('.hide-on-med-only').is(':visible');
  }
});

