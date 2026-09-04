import { useCallback, useEffect, useState } from 'react';
import Landing from './Landing';
import App from './App';

/**
 * Hash routing, deliberately without a router dependency.
 *
 * Two routes is not worth 12 KB of react-router, and a hash route works on any
 * static host with no server rewrite rules — which matters because this is meant
 * to deploy as a static site.
 *
 *   /        the landing page
 *   /#/app   the application
 */
function currentRoute(): 'landing' | 'app' {
  return window.location.hash.replace(/^#/, '').startsWith('/app') ? 'app' : 'landing';
}

export default function Root() {
  const [route, setRoute] = useState<'landing' | 'app'>(currentRoute);

  useEffect(() => {
    const onChange = () => setRoute(currentRoute());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  // Landing and app are separate documents as far as the reader is concerned,
  // so entering one should start at its top rather than inherit a scroll offset.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [route]);

  const launch = useCallback(() => {
    window.location.hash = '/app';
  }, []);

  const home = useCallback(() => {
    window.location.hash = '';
  }, []);

  return route === 'app' ? <App onExit={home} /> : <Landing onLaunch={launch} />;
}
