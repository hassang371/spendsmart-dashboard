import React from "react";
import Button from "./Button";
import { Twitter, Instagram, Youtube, Disc } from "lucide-react";

const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-brand-dark pt-24 pb-12 text-white">
      <div className="container mx-auto px-4">
        {/* Big Blocky Sections */}
        <div className="grid gap-6 md:grid-cols-2">
          {/* Left Block - Brand */}
          <div className="flex flex-col justify-between rounded-[2.5rem] bg-brand-orange p-10 text-brand-dark min-h-[500px] relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 transition-transform group-hover:scale-150 duration-700 pointer-events-none">
              <div className="w-64 h-64 bg-black rounded-full mix-blend-overlay opacity-10 blur-3xl" />
            </div>
            <div>
              <h2 className="font-display text-[15vw] md:text-[12rem] font-bold leading-[0.8] tracking-tighter uppercase select-none">
                SCALE
              </h2>
            </div>
            <div className="mt-auto relative z-10">
              <p className="font-display text-5xl md:text-7xl font-bold uppercase leading-[0.9] tracking-tight">
                Money, <br /> Measured.
              </p>
            </div>
          </div>

          {/* Right Block - Marquee CTA */}
          <div className="flex flex-col rounded-[2.5rem] bg-brand-blue text-brand-dark min-h-[500px] overflow-hidden relative">
            <div className="absolute inset-0 p-10 flex flex-col items-center justify-center text-center z-10 gap-10">
              <h2 className="font-display text-6xl md:text-8xl font-bold leading-[0.85] tracking-tighter uppercase">
                Get Scale <br />{" "}
                <span
                  className="text-transparent"
                  style={{
                    WebkitTextStroke: "2px #060d14",
                  }}
                >
                  Now.
                </span>
              </h2>
              <div className="flex flex-wrap gap-4 justify-center w-full">
                <Button
                  variant="white"
                  href="/login"
                  className="!px-8 !py-4 !text-xl shadow-hard hover:shadow-hard-lg border-2 border-black"
                >
                  Download App
                </Button>
                <Button
                  variant="dark"
                  href="/dashboard"
                  className="!px-8 !py-4 !text-xl shadow-hard hover:shadow-hard-lg"
                >
                  Web Dashboard
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Large Green Download Banner - Replaced with more content links if needed, or kept */}
        <div className="mt-6 rounded-[2.5rem] bg-brand-green p-10 md:p-16 text-brand-dark flex flex-col md:flex-row items-start justify-between gap-10">
          <div className="max-w-3xl">
            <h2 className="font-display text-5xl md:text-7xl font-bold uppercase leading-[0.9] tracking-tighter italic">
              DOWNLOAD SCALE. <br />
              THEN MAKE IT ALL HAPPEN.
            </h2>
          </div>
          <div className="grid grid-cols-2 gap-x-12 gap-y-4 font-display text-xl md:text-2xl font-bold uppercase text-right">
            <a
              href="#"
              className="hover:underline decoration-4 underline-offset-4"
            >
              Home
            </a>
            <a
              href="#"
              className="hover:underline decoration-4 underline-offset-4"
            >
              Security
            </a>
            <a
              href="#"
              className="hover:underline decoration-4 underline-offset-4"
            >
              Features
            </a>
            <a
              href="#"
              className="hover:underline decoration-4 underline-offset-4"
            >
              Download
            </a>
            <a
              href="#"
              className="hover:underline decoration-4 underline-offset-4"
            >
              Get Started
            </a>
            <a
              href="#"
              className="hover:underline decoration-4 underline-offset-4"
            >
              Guides
            </a>
          </div>
        </div>

        {/* Bottom Socials & Copyright */}
        <div className="mt-6 grid gap-6 md:grid-cols-4">
          <div className="bg-white rounded-[2rem] aspect-square flex items-center justify-center text-black hover:bg-brand-yellow transition-colors group cursor-pointer border-2 border-transparent hover:border-black">
            <Disc className="w-20 h-20 group-hover:rotate-180 transition-transform duration-500" />
          </div>
          <div className="bg-white rounded-[2rem] aspect-square flex items-center justify-center text-black hover:bg-brand-violet transition-colors group cursor-pointer border-2 border-transparent hover:border-black">
            <Twitter className="w-20 h-20 group-hover:scale-110 transition-transform" />
          </div>
          <div className="bg-white rounded-[2rem] aspect-square flex items-center justify-center text-black hover:bg-brand-coral transition-colors group cursor-pointer border-2 border-transparent hover:border-black">
            <Instagram className="w-20 h-20 group-hover:scale-110 transition-transform" />
          </div>
          <div className="bg-white rounded-[2rem] aspect-square flex items-center justify-center text-black hover:bg-brand-blue transition-colors group cursor-pointer border-2 border-transparent hover:border-black">
            <Youtube className="w-20 h-20 group-hover:scale-110 transition-transform" />
          </div>
        </div>

        <div className="mt-12 flex flex-col md:flex-row justify-between items-end gap-6 text-gray-400 font-sans text-sm font-bold uppercase">
          <div className="flex gap-6">
            <a href="#" className="hover:text-white">
              Privacy Notice
            </a>
            <a href="#" className="hover:text-white">
              Terms of Service
            </a>
            <a href="#" className="hover:text-white">
              Brand Assets
            </a>
          </div>
          <p>© {currentYear} SCALE LABS, INC.</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
