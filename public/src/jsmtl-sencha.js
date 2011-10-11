// JS-MONTREAL
// Sencha Touch mobile version


(function(){

var mainView = {

  id: 'mainPanel',
  fullscreen: true,
  cls: 'mobile',
  defaults: {
    styleHtmlContent: true
  },
  items: [{
    iconCls: 'favorites',
    title: 'Current',
    scroll: 'vertical'
  },{
    iconCls: 'favorites',
    title: 'Previously',
    html: 'bbq'
  },{
    iconCls: 'default',
    title: 'Where',
    items: {
      xtype: 'map',
      useCurrentLocation: true
    }
  },{
    iconCls: 'default',
    title: 'About',
    html: 'About JS-MONTREAL'
  }],

  tabBar: {
    dock: 'bottom',
    scroll: {
      direction: 'horizontal',
      useIndicators: true
    },
    layout: {
      pack: 'center'
    }
  }
};

var jsmtl = new Ext.Application({
  name: 'jsmtl',

  launch: function() {
    this.viewport = new Ext.TabPanel(mainView);
  }
});

jsmtl.on('launch', function(app){

  Ext.Ajax.request({
    url: "/meetups/current",
    callback: function(options, success, response){
      //console.debug(app.viewport);
      app.viewport.items.getAt(0).update(response.responseText);
    }
  });

});




})();