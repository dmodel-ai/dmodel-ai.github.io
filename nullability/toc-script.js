// Script to highlight the current section in TOC while scrolling and handle aggressive fade effects
document.addEventListener('DOMContentLoaded', function() {
  const sections = document.querySelectorAll('h1[id], h2[id], h3[id], h4[id], h5[id]');
  const tocLinks = document.querySelectorAll('#TOC a');
  const toc = document.getElementById('TOC');
  const body = document.body;
  
  function handleTOCEffect() {
    // Find the section currently in view
    let currentSectionId = '';
    const scrollPosition = window.scrollY;
    
    // Get the section that's currently most visible
    sections.forEach(section => {
      const sectionTop = section.offsetTop - 100; // Offset to trigger highlight a bit earlier
      if (scrollPosition >= sectionTop) {
        currentSectionId = '#' + section.id;
      }
    });
    
    // Remove active class from all links
    tocLinks.forEach(link => {
      link.classList.remove('toc-active');
    });
    
    // Add active class to current section's link
    if (currentSectionId) {
      const currentLink = document.querySelector(`#TOC a[href="${currentSectionId}"]`);
      if (currentLink) {
        currentLink.classList.add('toc-active');
        
        // Only auto-scroll the TOC on desktop (not on mobile)
        if (window.innerWidth > 1000) {
          // Make the TOC scroll to show the active item if needed
          const tocRect = toc.getBoundingClientRect();
          const linkRect = currentLink.getBoundingClientRect();
          
          // If the active item is outside the visible area of TOC
          if (linkRect.top < tocRect.top || linkRect.bottom > tocRect.bottom) {
            // Scroll the TOC element itself, not the window
            toc.scrollTop = toc.scrollTop + (linkRect.top - tocRect.top) - (tocRect.height / 2) + (linkRect.height / 2);
          }
        }
      }
    }
    
    // Handle fade in/out based on scroll position
    // Add/remove class for top of page
    if (scrollPosition < 100) {
      body.classList.add('at-top');
    } else {
      body.classList.remove('at-top');
    }
  }
  
  // Run on scroll
  window.addEventListener('scroll', handleTOCEffect);
  
  // Run once on load
  handleTOCEffect();
  
  // Add hover detection for touch devices
  let touchTimeout;
  toc.addEventListener('touchstart', function() {
    clearTimeout(touchTimeout);
    toc.style.opacity = '1';
  });
  
  toc.addEventListener('touchend', function() {
    clearTimeout(touchTimeout);
    touchTimeout = setTimeout(function() {
      if (!body.classList.contains('at-top')) {
        toc.style.opacity = '0.2';
      }
    }, 2000); // Fade back after 2 seconds
  });
});
