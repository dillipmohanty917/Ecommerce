$(document).ready(function(){
    var debounceTimer;

    $('#partner_search').on('input', function(){
        var searchText = $(this).val();
        
        clearTimeout(debounceTimer);
        // Clear dropdown content immediately when input is empty
        if (!searchText.trim()) {
          $('#show-list').empty();
          $('#selectedPartnerId').val("");
          return;
      }
        debounceTimer = setTimeout(function() {
            if(searchText){
                $.ajax({
                    url: '/partner/names',
                    type: 'GET',
                    data: { filter: searchText },
                    success: function(data) {
                        $('#show-list').empty();
                        data.forEach(function(partner) {
                            const item_name = partner.name;
                            const substring = new RegExp(searchText, "gi");
                            const original = item_name;
                            let x = original.replace(substring, `<strong>${searchText}</strong>`);
                            $('#show-list').append(`
                                <div class='dropdown_data_pos' data-partner-id=${partner.id} data-partner-name="${partner.name}">
                                    <div class='dropdown_item_name col'>${x}</div>
                                    <div class='mar-l-r-0 d-flex'>
                                        <div class='dropdown_item_details col-7'>
                                            <span>City: <strong>${partner.city}</strong></span>
                                        </div>                                                 
                                        <div class='dropdown_item_details col-5'>
                                            <span>ID: <strong>${partner.id}</strong></span>
                                        </div> 
                                    </div>
                                </div>
                            `);
                        });
                    },
                    error: function(xhr, status, error) {
                        console.error('Error fetching data:', error);
                    }
                });
            }
        }, 200);
    });


    $(document).on('click', '.dropdown_data_pos' ,function(){
        console.log('event')
        var partner_id = $(this).data('partner-id');
        var partner_name = $(this).data('partner-name');
        $('#partner_search').val(partner_name);
        $('#selectedPartnerId').val(partner_id);
        $('#show-list').empty();
        $('#partner_search').focus();

      });
});