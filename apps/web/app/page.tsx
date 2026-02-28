'use client';

import { useEffect, useState } from 'react';
import Script from 'next/script';
import { WEBFLOW_LANDING_HTML } from '@/lib/webflow-html';
import './webflow-landing.css';
import './webflow-overrides.css';

export default function Home() {
  const [gsapReady, setGsapReady] = useState(false);
  const [coreLibsReady, setCoreLibsReady] = useState(false);
  const [slaterScriptsLoaded, setSlaterScriptsLoaded] = useState(0);

  useEffect(() => {
    // Inject Webflow external CSS into document head
    const link = document.createElement('link');
    link.href = 'https://cdn.prod.website-files.com/680905cfdc450738383648a6/css/sui-slush-staging.shared.af10f7987.min.css';
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.integrity = 'sha384-rxD3mH4xSMVwaBQeNXbiKNTrCQoFFUP2bXG68tATZpCE/LHKIURVmVf3mQ4sOTNA';
    link.crossOrigin = 'anonymous';
    link.id = 'webflow-external-css';
    document.head.appendChild(link);

    // Disable Barba.js page transitions (Next.js handles routing)
    window.history.scrollRestoration = 'manual';

    // Log script loading for debugging
    console.log('[SCALE] Page component mounted, CSS injected');

    return () => {
      // Cleanup: remove the link when component unmounts
      const existingLink = document.getElementById('webflow-external-css');
      if (existingLink) {
        document.head.removeChild(existingLink);
      }
    };
  }, []);

  // Trigger Webflow initialization after all scripts are loaded
  useEffect(() => {
    if (gsapReady && coreLibsReady) {
      console.log('[SCALE] All dependencies ready, waiting for initialization...');

      // Wait for next tick to ensure all scripts have executed
      setTimeout(() => {
        // Initialize Webflow
        if (typeof window !== 'undefined' && (window as any).Webflow) {
          console.log('[SCALE] Triggering Webflow.destroy() and Webflow.ready()');
          (window as any).Webflow.destroy();
          (window as any).Webflow.ready();
          (window as any).Webflow.require('ix2').init();
          console.log('[SCALE] Webflow initialized');
        } else {
          console.warn('[SCALE] Webflow object not found on window');
        }

        // Prevent Barba.js from hijacking navigation (Next.js handles routing)
        if (typeof window !== 'undefined' && (window as any).barba) {
          console.log('[SCALE] Barba.js detected - preventing navigation hijacking');
          // Destroy any existing Barba instance
          if ((window as any).barba.destroy) {
            (window as any).barba.destroy();
          }
        }

        console.log('[SCALE] All initialization complete');
      }, 100);
    }
  }, [gsapReady, coreLibsReady]);

  // Re-trigger initialization after Slater scripts load
  useEffect(() => {
    if (slaterScriptsLoaded === 2) {
      console.log('[SCALE] Both Slater scripts loaded, re-triggering initialization...');

      // Use longer delay to ensure DOM is fully painted
      setTimeout(() => {
        // Trigger jQuery ready handlers manually
        if (typeof window !== 'undefined' && (window as any).$) {
          console.log('[SCALE] Triggering jQuery ready handlers');
          (window as any).$(document).ready(() => {
            console.log('[SCALE] jQuery ready callback executed');
          });

          // Also trigger using jQuery's internal ready queue
          if ((window as any).$.fn.ready) {
            (window as any).$(document).trigger('ready');
          }
        }

        // Dispatch custom DOM ready event to trigger script re-initialization
        const event = new Event('DOMContentLoaded');
        document.dispatchEvent(event);
        console.log('[SCALE] DOMContentLoaded event dispatched');

        // Re-initialize Webflow to ensure all elements are bound
        if (typeof window !== 'undefined' && (window as any).Webflow) {
          (window as any).Webflow.destroy();
          (window as any).Webflow.ready();
          console.log('[SCALE] Webflow re-initialized after Slater scripts');
        }

        // Check if menu button exists and manually attach click handler
        const menuButton = document.querySelector('#menuButton');
        if (menuButton) {
          console.log('[SCALE] Menu button found:', menuButton);

          // Check if it already has click listeners
          const existingHandler = (menuButton as any)._clickHandler;
          if (!existingHandler) {
            console.log('[SCALE] Attaching manual click handler to menu button');
            const clickHandler = () => {
              console.log('[SCALE] Menu button clicked!');
              const navContainer = document.querySelector('#navContainer');
              if (navContainer) {
                const isOpen = navContainer.classList.toggle('is--open');
                console.log('[SCALE] Toggled nav container open state:', isOpen);

                // Close menu when clicking outside
                if (isOpen) {
                  const closeHandler = (e: MouseEvent) => {
                    if (!(e.target as Element).closest('.nav-inner')) {
                      navContainer.classList.remove('is--open');
                      document.removeEventListener('click', closeHandler);
                      console.log('[SCALE] Menu closed by clicking outside');
                    }
                  };
                  setTimeout(() => document.addEventListener('click', closeHandler), 100);
                }
              }
            };
            menuButton.addEventListener('click', clickHandler);
            (menuButton as any)._clickHandler = clickHandler; // Mark as handled
          }
        } else {
          console.warn('[SCALE] Menu button #menuButton not found in DOM');
        }

        // Find and log all interactive elements for debugging
        const plusIcons = document.querySelectorAll('[data-accordion-toggle], [class*="plus"], [class*="expand"]');
        console.log('[SCALE] Found', plusIcons.length, 'potential accordion/expand elements');
        if (plusIcons.length > 0) {
          console.log('[SCALE] First accordion element:', plusIcons[0]);
        }

        // Check for tab elements and manually initialize
        const tabsWrapper = document.querySelector('[data-tabs="wrapper"]');
        const tabButtons = document.querySelectorAll('[data-tabs="content-item"]');
        const tabVisuals = document.querySelectorAll('[data-tabs="visual-item"]');
        console.log('[SCALE] Found tabs wrapper:', tabsWrapper);
        console.log('[SCALE] Found', tabButtons.length, 'tab buttons');
        console.log('[SCALE] Found', tabVisuals.length, 'tab visuals');

        // Manually attach tab click handlers
        if (tabButtons.length > 0 && tabVisuals.length > 0) {
          tabButtons.forEach((button, index) => {
            button.addEventListener('click', () => {
              console.log('[SCALE] Tab', index, 'clicked');

              // Remove active class from all buttons and visuals
              tabButtons.forEach(btn => btn.classList.remove('active'));
              tabVisuals.forEach(visual => visual.classList.remove('active'));

              // Add active class to clicked button and corresponding visual
              button.classList.add('active');
              if (tabVisuals[index]) {
                tabVisuals[index].classList.add('active');
              }
            });
          });

          // Set first tab as active by default
          if (tabButtons[0] && tabVisuals[0]) {
            tabButtons[0].classList.add('active');
            tabVisuals[0].classList.add('active');
          }

          console.log('[SCALE] Tab handlers attached');
        }

        // Check global objects available
        console.log('[SCALE] Available globals:', {
          jQuery: typeof (window as any).$,
          gsap: typeof (window as any).gsap,
          Webflow: typeof (window as any).Webflow,
          barba: typeof (window as any).barba,
          Lottie: typeof (window as any).lottie,
          Lenis: typeof (window as any).Lenis
        });

        // Prevent navigation links from causing 404s
        const navLinks = document.querySelectorAll('.nav-inner-list a[href^="/"]');
        navLinks.forEach(link => {
          link.addEventListener('click', (e) => {
            e.preventDefault();
            const href = (link as HTMLAnchorElement).href;
            console.log('[SCALE] Navigation link clicked, preventing default:', href);

            // Close menu if open
            const navContainer = document.querySelector('#navContainer');
            if (navContainer?.classList.contains('is--open')) {
              navContainer.classList.remove('is--open');
            }

            // Show alert or handle navigation
            alert(`This is a landing page demo. The link "${href}" would navigate to your actual dashboard.`);
          });
        });
        console.log('[SCALE] Prevented', navLinks.length, 'navigation links from causing 404s');
      }, 500); // Increased delay
    }
  }, [slaterScriptsLoaded]);

  return (
    <>
      {/* Webflow HTML Content */}
      <div
        className="webflow-landing"
        dangerouslySetInnerHTML={{ __html: WEBFLOW_LANDING_HTML }}
      />

      {/* External Scripts - Load in dependency order */}
      <Script
        src="https://d3e54v103j8qbb.cloudfront.net/js/jquery-3.5.1.min.dc5e7f18c8.js"
        strategy="beforeInteractive"
        integrity="sha256-9/aliU8dGd2tb6OSsuzixeV4y/faTqgFtohetphbbj0="
        crossOrigin="anonymous"
        onLoad={() => console.log('[SCALE] jQuery loaded')}
      />

      {/* GSAP Core + Modules */}
      <Script
        src="https://cdn.jsdelivr.net/npm/gsap@3.12.7/dist/gsap.min.js"
        strategy="afterInteractive"
        onLoad={() => console.log('[SCALE] GSAP loaded')}
      />
      <Script
        src="https://cdn.jsdelivr.net/npm/gsap@3.12.7/dist/ScrollTrigger.min.js"
        strategy="afterInteractive"
        onLoad={() => console.log('[SCALE] ScrollTrigger loaded')}
      />
      <Script
        src="https://cdn.jsdelivr.net/npm/gsap@3.12.7/dist/CustomEase.min.js"
        strategy="afterInteractive"
        onLoad={() => console.log('[SCALE] CustomEase loaded')}
      />
      <Script
        src="https://cdn.jsdelivr.net/npm/gsap@3.12.7/dist/Draggable.min.js"
        strategy="afterInteractive"
        onLoad={() => console.log('[SCALE] Draggable loaded')}
      />
      <Script
        src="https://cdn.jsdelivr.net/npm/gsap@3.12.7/dist/Observer.min.js"
        strategy="afterInteractive"
        onLoad={() => console.log('[SCALE] Observer loaded')}
      />
      <Script
        src="https://cdn.jsdelivr.net/npm/gsap@3.12.7/dist/Flip.min.js"
        strategy="afterInteractive"
        onLoad={() => console.log('[SCALE] Flip loaded')}
      />
      <Script
        src="https://assets.greensock.com/v3/InertiaPlugin.min.js"
        strategy="afterInteractive"
        onLoad={() => console.log('[SCALE] InertiaPlugin loaded')}
        onError={(e) => console.error('[SCALE] InertiaPlugin failed to load:', e)}
      />
      <Script
        src="https://assets.greensock.com/v3/SplitText.min.js"
        strategy="afterInteractive"
        onLoad={() => {
          console.log('[SCALE] SplitText loaded - GSAP ready');
          setGsapReady(true);
        }}
        onError={(e) => {
          console.error('[SCALE] SplitText failed to load:', e);
          // Set gsapReady anyway so the app doesn't hang
          console.warn('[SCALE] Setting gsapReady=true despite SplitText error');
          setGsapReady(true);
        }}
      />

      {/* Page Transitions, Animations, Smooth Scroll */}
      <Script
        src="https://cdn.jsdelivr.net/npm/@barba/core@2.9.7/dist/barba.umd.min.js"
        strategy="afterInteractive"
        onLoad={() => console.log('[SCALE] Barba loaded')}
      />
      <Script
        src="https://cdn.jsdelivr.net/npm/lottie-web@5.12.2/build/player/lottie.min.js"
        strategy="afterInteractive"
        onLoad={() => console.log('[SCALE] Lottie loaded')}
      />
      <Script
        src="https://unpkg.com/lenis@1.1.14/dist/lenis.min.js"
        strategy="afterInteractive"
        onLoad={() => console.log('[SCALE] Lenis loaded')}
      />

      {/* Webflow Site Scripts */}
      <Script
        src="https://cdn.prod.website-files.com/680905cfdc450738383648a6/js/sui-slush-staging.a0aa6ca1.5e040c4c6f25cfaa.js"
        strategy="afterInteractive"
        integrity="sha384-LayizkkxA+rTQh6O8Oco82BNpeR+XiyVJ8tsbo2bbb5N0JPicETIMCVqLXqYACOA"
        crossOrigin="anonymous"
        onLoad={() => {
          console.log('[SCALE] Webflow site script loaded - Core libs ready');
          setCoreLibsReady(true);
        }}
      />

      {/* Slater App Custom Scripts - Only load after GSAP and core libs are ready */}
      {gsapReady && coreLibsReady && (
        <>
          <Script
            src="https://assets.slater.app/slater/14111/46342.js"
            strategy="afterInteractive"
            onLoad={() => {
              console.log('[SCALE] Slater script 1 (geolocation) loaded');
              setSlaterScriptsLoaded(prev => prev + 1);
            }}
          />
          <Script
            src="https://assets.slater.app/slater/14111/42806.js"
            strategy="afterInteractive"
            onLoad={() => {
              console.log('[SCALE] Slater script 2 (interactions) loaded');
              setSlaterScriptsLoaded(prev => prev + 1);
            }}
            onError={(e) => console.error('[SCALE] Slater script 2 error:', e)}
          />
        </>
      )}

      {/* HubSpot Forms */}
      <Script src="//js.hsforms.net/forms/embed/v2.js" strategy="lazyOnload" />
    </>
  );
}
