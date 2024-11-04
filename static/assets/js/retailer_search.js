$(document).ready(function(){
    var debounceTimer;

    $('#retailer_search').on('input', function(){
        var searchText = $(this).val();
        clearTimeout(debounceTimer);
        // Clear dropdown content immediately when input is empty
        if (!searchText.trim()) {
          $('#show-list').empty();
          $('#selectedRetailerId').val("");
          return;
      }
        debounceTimer = setTimeout(function() {
            if(searchText){
                $.ajax({
                    url: '/retailer/names',
                    type: 'GET',
                    data: { filter: searchText },
                    success: function(data) {
                        $('#show-list').empty();
                        console.log(data,"dta")
                        data.forEach(function(partner) {
                            const item_name = partner.name;
                            const substring = new RegExp(searchText, "gi");
                            const original = item_name;
                            let x = original.replace(substring, `<strong>${searchText}</strong>`);
                            $('#show-list').append(`
                            <div class='dropdown_data_pos' data-partner-id=${partner.id} data-partner-name="${partner.name}" data-partner-id=${partner.city}>
                                <div class='dropdown_item_name col'>${x}</div>
                                <div class='mar-l-r-0 d-flex'>
                                        <div class='dropdown_item_details col-7'>
                                            <span>Phone: <strong>${partner.user}</strong></span>
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
        var partner_name = $(this).data('partner-name');
        var partner_id = $(this).data('partner-id');
        $('#selectedRetailerId').val(partner_id);
        $('#retailer_search').val(partner_name);
        $('#show-list').empty();
        $('#retailer_search').focus();

      });
});